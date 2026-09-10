-- writing-for-humans pandoc 필터.
-- Markdown 원본은 GitHub에서 그대로 읽히는 문법만 쓴다. 이 필터가 그 문법을
-- HTML 쉘의 클래스와 Word용 자산으로 옮긴다.
--   ![캡션](x.svg)   → HTML: <figure class="diagram">인라인 SVG</figure> / docx: x.png가 있으면 그것으로
--   > [!NOTE] …      → HTML: <div class="note"> (GitHub alert 문법)
--   > 인용 …         → 그대로 blockquote (근거 인용)
--   표               → HTML: <div class="table-wrap"> 로 감싼다
--   ## 출처 절의 목록 → <div class="sources">

local is_html = FORMAT:match("html") ~= nil
local is_docx = FORMAT == "docx"

local function read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local s = f:read("a")
  f:close()
  return s
end

local function file_exists(path)
  local f = io.open(path, "r")
  if f then f:close() return true end
  return false
end

local function html_escape(s)
  return (s:gsub("[&<>\"]", { ["&"] = "&amp;", ["<"] = "&lt;", [">"] = "&gt;", ['"'] = "&quot;" }))
end

function Figure(fig)
  local plain = fig.content[1]
  local img = plain and plain.content and plain.content[1]
  if not img or img.t ~= "Image" then return nil end
  local src = img.src
  if is_html and src:match("%.svg$") then
    local svg = read_file(src)
    if not svg then
      io.stderr:write("filters.lua: SVG를 열 수 없음: " .. src .. "\n")
      return nil
    end
    svg = svg:gsub("^%s*<%?xml[^>]*%?>%s*", "")
    local cap = html_escape(pandoc.utils.stringify(fig.caption))
    return pandoc.RawBlock("html",
      '<figure class="diagram">\n' .. svg .. '\n<figcaption>' .. cap .. '</figcaption>\n</figure>')
  end
  if is_docx and src:match("%.svg$") then
    local png = src:gsub("%.svg$", ".png")
    if file_exists(png) then
      img.src = png
      plain.content[1] = img
      fig.content[1] = plain
      return fig
    end
    io.stderr:write("filters.lua: " .. png .. " 없음. Word에는 PNG를 넣는다 (diagram-design 문서 적용 규칙).\n")
  end
  return nil
end

function BlockQuote(bq)
  local first = bq.content[1]
  if first and first.t == "Para" and first.content[1] and first.content[1].t == "Str" then
    local marker = first.content[1].text:match("^%[!(%u+)%]$")
    if marker then
      -- "[!NOTE]" 토큰과 뒤따르는 줄바꿈을 떼고, 종류를 굵은 라벨로 남긴다
      table.remove(first.content, 1)
      while first.content[1] and (first.content[1].t == "SoftBreak" or first.content[1].t == "LineBreak") do
        table.remove(first.content, 1)
      end
      local labels = { NOTE = "참고", TIP = "팁", IMPORTANT = "중요", WARNING = "주의", CAUTION = "경고" }
      table.insert(first.content, 1, pandoc.Strong({ pandoc.Str(labels[marker] or marker) }))
      table.insert(first.content, 2, pandoc.Str(" "))
      if not is_html then
        bq.content[1] = first
        return bq
      end
      return pandoc.Div(bq.content, pandoc.Attr("", { "note", "note-" .. marker:lower() }))
    end
  end
  return nil
end

function Table(tbl)
  if not is_html then return nil end
  return pandoc.Div({ tbl }, pandoc.Attr("", { "table-wrap" }))
end

function Pandoc(doc)
  if not is_html then return nil end
  local blocks = doc.blocks
  for i, b in ipairs(blocks) do
    if b.t == "Header" and b.level == 2 and pandoc.utils.stringify(b) == "출처" then
      local j = i + 1
      while blocks[j] and blocks[j].t ~= "Header" do
        if blocks[j].t == "OrderedList" or blocks[j].t == "BulletList" then
          blocks[j] = pandoc.Div({ blocks[j] }, pandoc.Attr("", { "sources" }))
        end
        j = j + 1
      end
    end
  end
  doc.blocks = blocks
  return doc
end
