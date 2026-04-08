/**
 * HTML 내보내기
 * 에디터 콘텐츠를 자체 완결적(self-contained) HTML 파일로 내보냅니다.
 */

import { saveAs } from 'file-saver';

export function exportToHtml(html: string, filename = '탐구보고서'): void {
  const fullHtml = `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${filename}</title>
  <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: #f1f5f9;
      display: flex;
      justify-content: center;
      padding: 40px 20px;
    }

    .page {
      width: 210mm;
      min-height: 297mm;
      padding: 25mm 20mm 30mm 20mm;
      background: #ffffff;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
      font-family: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont, 'Noto Sans KR', sans-serif;
      font-size: 11pt;
      line-height: 1.6;
      color: #1e293b;
      word-break: keep-all;
      overflow-wrap: break-word;
    }

    h1 {
      font-size: 22pt;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin: 1.5rem 0 0.75rem;
      color: #0f172a;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 0.4rem;
    }
    h2 {
      font-size: 16pt;
      font-weight: 700;
      margin: 1.25rem 0 0.5rem;
      color: #1e293b;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 0.3rem;
    }
    h3 {
      font-size: 13pt;
      font-weight: 700;
      margin: 1rem 0 0.4rem;
      color: #334155;
    }

    p { margin: 0.4rem 0; }

    blockquote {
      border-left: 4px solid #3b82f6;
      background: #f8fafc;
      margin: 1rem 0;
      padding: 0.75rem 1rem;
      border-radius: 0 8px 8px 0;
      color: #475569;
      font-style: italic;
    }

    hr {
      border: none;
      border-top: 1px solid #e2e8f0;
      margin: 2rem 0;
    }

    table {
      border-collapse: collapse;
      table-layout: fixed;
      width: 100%;
      margin: 1rem 0;
      font-size: 10pt;
    }
    td, th {
      min-width: 2em;
      border: 1px solid #e2e8f0;
      padding: 6px 10px;
      vertical-align: top;
    }
    th {
      font-weight: 700;
      background: #f8fafc;
      text-align: left;
    }

    img {
      max-width: 100%;
      height: auto;
      display: block;
      margin: 1rem auto;
      border-radius: 6px;
    }

    ul, ol {
      padding-left: 1.5rem;
      margin: 0.6rem 0;
    }
    li p { margin: 0; }

    a {
      color: #2563eb;
      text-decoration: underline;
    }

    code {
      background: #f1f5f9;
      border-radius: 4px;
      padding: 2px 5px;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.9em;
      color: #e11d48;
    }

    mark {
      border-radius: 2px;
      padding: 0 2px;
    }

    @media print {
      body { background: white; padding: 0; }
      .page {
        width: 100%;
        margin: 0;
        padding: 20mm;
        box-shadow: none;
        min-height: auto;
      }
    }

    .footer {
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid #e2e8f0;
      text-align: center;
      font-size: 9pt;
      color: #94a3b8;
    }
  </style>
</head>
<body>
  <div class="page">
    ${html}
    <div class="footer">
      Uni Foli에서 작성됨 · ${new Date().toLocaleDateString('ko-KR')}
    </div>
  </div>
</body>
</html>`;

  const blob = new Blob([fullHtml], { type: 'text/html;charset=utf-8' });
  saveAs(blob, `${filename}.html`);
}
