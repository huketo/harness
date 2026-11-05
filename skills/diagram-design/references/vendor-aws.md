# Vendor convention: AWS

Load this when an architecture or deployment diagram shows a workload running on AWS and the reader is an AWS audience (or the user asks for "AWS style"). AWS readers judge a diagram by AWS's own drawing conventions first; a flat VPC or a third-party S3 bucket is the first thing they notice.

This reference sits on top of [primitive-logos.md](primitive-logos.md) and the icon-node geometry in [type-architecture.md](type-architecture.md#icon-nodes). It **overrides** these SKILL.md defaults for the diagram it governs: the bottom legend strip, coral focal accents, the zone fill, and the zone eyebrow label. The §6 connector rules, the 4px grid, the complexity budget, and the accessible-SVG contract still apply unchanged.

Adapted from caru-ini/stack-diagram (MIT, see `LICENSE.stack-diagram`).

## Icons — AWS's own, nothing else

Fetch every AWS service and group icon from AWS's official package with the `aws/` prefix. A bare slug such as `dynamodb` goes through the third-party chain instead, so always write the prefix:

```bash
python3 scripts/logos.py fetch <logodir> \
  cloudfront:aws/CloudFront s3:aws/s3 elb:aws/alb fargate:aws/fargate rds:aws/rds \
  user:aws/General-User awscloud:aws/AWS-Cloud-logo vpc:aws/vpc \
  public:aws/Public-subnet private:aws/Private-subnet
```

- The `AWS-` / `Amazon-` prefix is optional; acronyms work (`s3`, `sqs`, `sns`, `ses`, `ecs`, `eks`, `ecr`, `elb`, `alb`, `nlb`, `iam`, `kms`, `msk`, `vpc`). A miss prints every name in the package.
- Group icons in the package: `AWS-Cloud-logo`, `Region`, `Virtual-private-cloud-VPC` (alias `vpc`), `Public-subnet`, `Private-subnet`. An Availability Zone has no icon.
- People and generic nodes use AWS's general icons (`General-User`, `General-Users`, `General-Client`, `General-Internet`, `General-Server`, …), not the monochrome primitive set. They ship a `_dark` variant; use the `lt`/`dk` pair.
- Keep the package and the fetched files out of repositories. AWS permits the icons in diagrams; redistribution is not confirmed.

## Nodes

Service icons carry their own colored square, so they sit **bare**: no white tile, 48×48 at the tile position `(cx-24, top)`. Name and sublabel positions follow the icon-node geometry.

```svg
<image href="%%LOGO_fargate%%" x="648" y="216" width="48" height="48"/>
<text class="name halo" x="672" y="284" text-anchor="middle">AWS Fargate</text>
<text class="sub halo" x="672" y="300" text-anchor="middle">api tasks</text>
```

- Name nodes by the full service name: `Amazon S3`, `AWS Fargate`, not `S3` / `Fargate`. A short form such as `ALB` goes in the sublabel.
- A name wider than the 128px box takes two lines (`<tspan x="cx" dy="16">`). `Amazon` / `AWS` stays on the first line with the next word. A two-line name moves the sublabel to `top+100` and the node-box bottom to `top+112`; vertical connectors leave from that bottom.
- General icons sit at 32×32, centered in the 48px slot `(cx-16, top+8)`.

## Groups

Square corners, outline only (no fill, no tint), label in ink at the top-left. The group icon is 32×32 flush in the corner; the label text starts 8px to its right.

| Group | Stroke | Dash | Icon |
|---|---|---|---|
| AWS Cloud | `ink` | solid | `AWS-Cloud-logo` (`lt`/`dk` pair) |
| Region | `#00A4A6` | `4 4` | `Region` |
| Availability Zone | `#00A4A6` | `4 4` | none; label at `(x+12, y+20)` |
| VPC | `#8C4FFF` | solid | `Virtual-private-cloud-VPC` |
| Public subnet | `#7AA116` | solid | `Public-subnet` |
| Private subnet | `#00A4A6` | solid | `Private-subnet` |

```svg
<rect class="aws-group" x="360" y="120" width="584" height="384" style="stroke:#8C4FFF"/>
<image href="%%LOGO_vpc%%" x="360" y="120" width="32" height="32"/>
<text class="group-label" x="400" y="140">VPC</text>
```

```css
.aws-group { fill: none; stroke: var(--ink); stroke-width: 1.5; }
.aws-group.dashed { stroke-dasharray: 4 4; }
```

- Show public and private subnets inside a VPC whenever the split is known or safely inferable: an internet-facing load balancer is public; application tasks and databases are private.
- Group extents follow the icon-node group rule (`leftmost cx-88` … `rightmost cx+88`, top `= first tile top-48`, bottom `≥ last tile top+120`), with nested groups inset ≥24px on the sides and bottom and ≥48px below the parent's top edge.
- Group labels use the brand's own casing (`AWS Cloud`, `VPC`, `Public subnet`); no uppercase eyebrow.

## Edges

One color (`ink`) with an open arrowhead. Dashed for deploy-time or dev-time relationships. Labels use plain `.el` styling with the opaque mask; never accent.

```svg
<marker id="[slug]-open" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
  <path class="mk-open" d="M1 1 L9 5 L1 9"/>
</marker>
<path class="e aws" d="M500 240 H644" marker-end="url(#[slug]-open)"/>
```

```css
.e.aws { stroke: var(--ink); stroke-width: 1.5; }
.mk-open { fill: none; stroke: var(--ink); stroke-width: 1.5; }
```

## What this convention drops

- **No legend.** One edge color and AWS icons need none.
- **No coral.** Emphasis comes from the request path's position and direction, not color.
- **No zone fill or eyebrow.** Groups are AWS outlines, as above.

## Checklist

- [ ] Every AWS service and group icon came from `aws/` (manifest `source: aws`)?
- [ ] Public/private subnets shown where the split is known or inferable?
- [ ] Full service names, `Amazon`/`AWS` on the first line?
- [ ] One edge color, open arrowheads, no legend, no coral?
- [ ] Every edge-label mask sits clear of group outlines? Groups have no fill, so a mask over an outline cuts a visible gap in it; slide the label along its segment instead.
- [ ] Colophon credits `AWS Architecture Icons`?
