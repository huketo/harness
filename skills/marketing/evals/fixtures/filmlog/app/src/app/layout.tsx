import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: { default: 'Filmlog', template: '%s | Filmlog' },
  description: '필름 사진가들의 롤 아카이브와 커뮤니티',
  openGraph: { type: 'website', locale: 'ko_KR', siteName: 'Filmlog' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
