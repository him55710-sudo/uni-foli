import React, { useCallback, useRef, useMemo, useImperativeHandle, forwardRef, useState, useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import type { Editor, JSONContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import Highlight from '@tiptap/extension-highlight';
import FontFamily from '@tiptap/extension-font-family';
import { Table } from '@tiptap/extension-table';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import TableRow from '@tiptap/extension-table-row';
import Image from '@tiptap/extension-image';
import Link from '@tiptap/extension-link';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Placeholder from '@tiptap/extension-placeholder';
import { Minus, Plus } from 'lucide-react';

import { FontSize } from './extensions/FontSize';
import { LineHeight } from './extensions/LineHeight';
import { EditorToolbar } from './EditorToolbar';
import { A4Container } from './A4Container';
import { getResearchReportTemplate } from './templates/researchReport';
import { sourceRecordToCitationText } from '../../features/workshop/adapters/sourceAdapter';
import type {
  ContentPatch,
  FigureContentBlock,
  FormatPatch,
  MathContentBlock,
  ReportContentBlock,
  ReportMetadata,
  ReportPatch,
  SourceRecord,
  UniFoliReportSectionId,
} from '../../features/workshop/types/reportDocument';

import './TiptapEditor.css';

export interface TiptapEditorHandle {
  getJSON: () => JSONContent;
  getHTML: () => string;
  getMarkdown: () => string;
  insertTemplate: () => void;
  setContent: (content: any) => void;
  applyPatch: (patch: ReportPatch) => void;
  appendToSection: (sectionId: UniFoliReportSectionId, blocks: ReportContentBlock[]) => void;
  replaceSection: (sectionId: UniFoliReportSectionId, blocks: ReportContentBlock[]) => void;
  focusSection: (sectionId: UniFoliReportSectionId) => void;
  insertMathBlock: (block: MathContentBlock) => void;
  insertFigureBlock: (block: FigureContentBlock) => void;
  updateCoverMetadata: (metadata: ReportMetadata) => void;
  updateReferences: (sources: SourceRecord[]) => void;
}

interface TiptapEditorProps {
  initialContent?: JSONContent | string | null;
  onUpdate?: (json: JSONContent, html: string, text: string) => void;
  onJsonUpdate?: (json: JSONContent) => void;
  onHtmlUpdate?: (html: string) => void;
  readOnly?: boolean;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderInlineMarkdown(value: string): string {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/_([^_]+)_/g, '<em>$1</em>');
}

function markdownStringToHtml(markdown: string): string {
  const blocks: string[] = [];
  const lines = markdown.split(/\r?\n/);
  let paragraph: string[] = [];
  let listType: 'ul' | 'ol' | null = null;
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(`<p>${paragraph.map(renderInlineMarkdown).join('<br />')}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listType || !listItems.length) return;
    const tag = listType;
    blocks.push(`<${tag}>${listItems.map(item => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</${tag}>`);
    listType = null;
    listItems = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const bulletMatch = line.match(/^[-*]\s+(.*)$/);
    if (bulletMatch) {
      flushParagraph();
      if (listType !== 'ul') {
        flushList();
        listType = 'ul';
      }
      listItems.push(bulletMatch[1]);
      continue;
    }

    const orderedMatch = line.match(/^\d+\.\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType !== 'ol') {
        flushList();
        listType = 'ol';
      }
      listItems.push(orderedMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();

  return blocks.join('');
}

const SECTION_HEADING_LABELS: Record<UniFoliReportSectionId, string> = {
  cover: '표지',
  table_of_contents: '목차',
  motivation: 'I. 탐구 동기 및 목적',
  research_purpose: '탐구 목적',
  research_question: '탐구 질문',
  background_theory: 'II. 이론적 배경',
  prior_research: '선행연구',
  research_method: 'III. 탐구 방법',
  research_process: '탐구 과정',
  data_analysis: '데이터 분석',
  result: 'IV. 탐구 결과',
  conclusion: 'V. 결론 및 제언',
  limitation: '한계점',
  future_research: '후속 탐구',
  student_record_connection: '학생부 기록 연결',
  references: '참고 문헌',
  appendix: '부록',
};

const SECTION_HEADING_KEYWORDS: Record<UniFoliReportSectionId, string[]> = {
  cover: ['표지', 'title', 'cover', '탐구 보고서'],
  table_of_contents: ['목차', 'table of contents'],
  motivation: ['탐구 동기', '동기 및 목적', 'motivation', 'introduction'],
  research_purpose: ['탐구 목적', 'purpose'],
  research_question: ['탐구 질문', 'research question', '핵심 질문'],
  background_theory: ['이론적 배경', 'background', 'theory'],
  prior_research: ['선행연구', 'prior research'],
  research_method: ['탐구 방법', 'method'],
  research_process: ['탐구 과정', 'process'],
  data_analysis: ['데이터 분석', 'data analysis'],
  result: ['탐구 결과', 'result'],
  conclusion: ['결론', '제언', 'conclusion'],
  limitation: ['한계', 'limitation'],
  future_research: ['후속 탐구', 'future research', 'next step'],
  student_record_connection: ['학생부 기록', '생기부 기반', 'record connection'],
  references: ['참고 문헌', 'references', 'bibliography'],
  appendix: ['부록', 'appendix'],
};

function reportContentBlocksToTiptapNodes(blocks: ReportContentBlock[]): JSONContent[] {
  return blocks.flatMap((block) => {
    switch (block.type) {
      case 'heading':
        return [{ type: 'heading', attrs: { level: Math.min(block.level, 3) }, content: textContent(block.text) }];
      case 'list':
        return [
          {
            type: block.ordered ? 'orderedList' : 'bulletList',
            content: block.items.map((item) => ({
              type: 'listItem',
              content: [{ type: 'paragraph', content: textContent(item) }],
            })),
          },
        ];
      case 'quote':
        return [{ type: 'blockquote', content: [{ type: 'paragraph', content: textContent(block.text) }] }];
      case 'table':
        return [tableBlockToNode(block.headers, block.rows), ...(block.caption ? [paragraphNode(block.caption)] : [])];
      case 'math':
        return mathBlockToNodes(block);
      case 'figure':
        return figureBlockToNodes(block);
      case 'paragraph':
      default:
        return [paragraphNode(block.text)];
    }
  });
}

function paragraphNode(text: string): JSONContent {
  return { type: 'paragraph', content: textContent(text) };
}

function textContent(text: string): JSONContent[] | undefined {
  return text ? [{ type: 'text', text }] : undefined;
}

function tableBlockToNode(headers: string[], rows: string[][]): JSONContent {
  const headerRow = {
    type: 'tableRow',
    content: headers.map((header) => ({
      type: 'tableHeader',
      content: [paragraphNode(header)],
    })),
  };
  const bodyRows = rows.map((row) => ({
    type: 'tableRow',
    content: row.map((cell) => ({
      type: 'tableCell',
      content: [paragraphNode(cell)],
    })),
  }));
  return { type: 'table', content: [headerRow, ...bodyRows] };
}

function mathBlockToNodes(block: MathContentBlock): JSONContent[] {
  const mathText = block.displayMode === 'inline' ? `$${block.latex}$` : block.latex;
  const mathNode: JSONContent =
    block.displayMode === 'inline'
      ? paragraphNode(mathText)
      : { type: 'codeBlock', attrs: { language: 'latex' }, content: textContent(mathText) };
  return [mathNode, ...(block.caption ? [paragraphNode(`수식: ${block.caption}`)] : [])];
}

function figureBlockToNodes(block: FigureContentBlock): JSONContent[] {
  return [
    {
      type: 'image',
      attrs: {
        src: block.imageUrl,
        alt: block.altText,
        title: block.caption,
      },
    },
    paragraphNode(`그림: ${block.caption}${block.sourceId ? ` (출처: ${block.sourceId})` : ''}`),
  ];
}

function sourceRecordsToReferenceNodes(sources: SourceRecord[]): JSONContent[] {
  return [
    {
      type: 'orderedList',
      content: sources.map((source) => ({
        type: 'listItem',
        content: [paragraphNode(sourceRecordToCitationText(source))],
      })),
    },
  ];
}

function jsonContentToMarkdown(node: JSONContent | null | undefined): string {
  if (!node) return '';
  const children = (node.content || []).map(jsonContentToMarkdown).filter(Boolean);
  const text = node.text || children.join('\n\n');
  switch (node.type) {
    case 'doc':
      return children.join('\n\n');
    case 'heading':
      return `${'#'.repeat(Number(node.attrs?.level || 1))} ${text}`.trim();
    case 'paragraph':
      return text;
    case 'bulletList':
      return children.join('\n');
    case 'orderedList':
      return children.map((child, index) => `${index + 1}. ${child.replace(/^- /, '')}`).join('\n');
    case 'listItem':
      return `- ${children.join(' ').replace(/^- /, '')}`;
    case 'blockquote':
      return text
        .split('\n')
        .map((line) => `> ${line}`)
        .join('\n');
    case 'codeBlock':
      return `\`\`\`${node.attrs?.language || ''}\n${text}\n\`\`\``;
    case 'image':
      return `![${node.attrs?.alt || ''}](${node.attrs?.src || ''})`;
    case 'horizontalRule':
      return '---';
    case 'text':
      return node.text || '';
    default:
      return children.join('\n\n') || text;
  }
}

function findSectionRange(
  editor: Editor,
  sectionId: UniFoliReportSectionId,
): { headingPos: number; contentStart: number; contentEnd: number } | null {
  const keywords = SECTION_HEADING_KEYWORDS[sectionId] || [sectionId];
  let headingPos: number | null = null;
  let contentStart: number | null = null;
  let contentEnd: number | null = null;
  let headingLevel = 2;

  editor.state.doc.descendants((node, pos) => {
    if (node.type.name !== 'heading') {
      return true;
    }
    const level = Number(node.attrs.level || 2);
    const text = normalizeHeadingText(node.textContent || '');
    if (headingPos === null && keywords.some((keyword) => text.includes(normalizeHeadingText(keyword)))) {
      headingPos = pos;
      contentStart = pos + node.nodeSize;
      headingLevel = level;
      return true;
    }
    if (headingPos !== null && contentEnd === null && level <= headingLevel) {
      contentEnd = pos;
      return false;
    }
    return true;
  });

  if (headingPos === null || contentStart === null) {
    return null;
  }
  return {
    headingPos,
    contentStart,
    contentEnd: contentEnd ?? editor.state.doc.content.size,
  };
}

function normalizeHeadingText(value: string): string {
  return value
    .toLowerCase()
    .replace(/^[ivxlcdm]+\.\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function applyContentPatch(
  patch: ContentPatch,
  handlers: {
    appendToSection: (sectionId: UniFoliReportSectionId, blocks: ReportContentBlock[]) => void;
    replaceSection: (sectionId: UniFoliReportSectionId, blocks: ReportContentBlock[]) => void;
  },
) {
  if (patch.action === 'replace' || patch.action === 'rewrite') {
    handlers.replaceSection(patch.targetSection, patch.contentBlocks);
    return;
  }
  handlers.appendToSection(patch.targetSection, patch.contentBlocks);
}

function applyFormatPatch(
  editor: Editor,
  patch: FormatPatch,
  handlers: {
    updateCoverMetadata: (metadata: ReportMetadata) => void;
    updateReferences: (sources: SourceRecord[]) => void;
  },
) {
  if (patch.target === 'cover' && typeof patch.changes.metadata === 'object' && patch.changes.metadata) {
    handlers.updateCoverMetadata(patch.changes.metadata as ReportMetadata);
  }
  if (patch.target === 'citation' && Array.isArray(patch.changes.sources)) {
    handlers.updateReferences(patch.changes.sources as SourceRecord[]);
  }
  // TODO: Typography/numbering/toc changes should map to editor document attrs once those attrs exist.
  editor.commands.focus();
}

export function normalizeInitialStringContent(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (/<[a-z][\s\S]*>/i.test(trimmed)) {
    return trimmed;
  }
  return markdownStringToHtml(trimmed);
}

export const TiptapEditor = forwardRef<TiptapEditorHandle, TiptapEditorProps>(
  function TiptapEditor({ initialContent, onUpdate, onJsonUpdate, onHtmlUpdate, readOnly = false }, ref) {
    const contentRef = useRef<JSONContent | null>(null);
    const [zoom, setZoom] = useState(100);
    const [isResizing, setIsResizing] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Auto-scale on mount and resize to fit container if too narrow
    useEffect(() => {
      const handleResize = () => {
        if (!containerRef.current) return;
        const containerWidth = containerRef.current.clientWidth;
        const a4WidthPx = 210 * 3.7795275591; // 210mm to px approx (96dpi / 25.4)
        
        // If container is smaller than A4 width + padding, auto-scale down
        if (containerWidth < a4WidthPx + 64) {
          const autoScale = Math.floor(((containerWidth - 64) / a4WidthPx) * 100);
          setZoom(Math.max(30, Math.min(100, autoScale)));
        }
      };

      handleResize();
      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }, []);

    const handleImageUpload = useCallback((file: File, editorInstance: Editor) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const src = e.target?.result as string;
        if (src) {
          editorInstance.chain().focus().setImage({ src }).run();
        }
      };
      reader.readAsDataURL(file);
    }, []);

    // Resolve initial content — if it's a string (markdown/html), 
    // use it directly (Tiptap will parse HTML). If null, use template.
    const resolvedInitial = useMemo(() => {
      if (initialContent && typeof initialContent === 'object') {
        return initialContent as JSONContent;
      }
      if (typeof initialContent === 'string' && initialContent.trim()) {
        // Tiptap can parse HTML strings
        return normalizeInitialStringContent(initialContent);
      }
      return getResearchReportTemplate();
    }, [initialContent]);

    const extensions = useMemo(
      () => [
        StarterKit.configure({
          heading: { levels: [1, 2, 3] },
          bulletList: { keepMarks: true, keepAttributes: false },
          orderedList: { keepMarks: true, keepAttributes: false },
          blockquote: {},
          horizontalRule: {},
        }),
        Underline,
        TextStyle,
        Color,
        Highlight.configure({ multicolor: true }),
        FontFamily.configure({ types: ['textStyle'] }),
        FontSize,
        LineHeight,
        TextAlign.configure({ types: ['heading', 'paragraph'] }),
        Table.configure({ resizable: true }),
        TableRow,
        TableHeader,
        TableCell,
        Image.configure({ inline: false, allowBase64: true }),
        Link.configure({ openOnClick: false }),
        TaskList,
        TaskItem.configure({ nested: true }),
        Placeholder.configure({
          placeholder: ({ node }) => {
            if (node.type.name === 'heading') return '제목을 입력하세요...';
            return '이곳에 내용을 작성하세요...';
          },
        }),
      ],
      [],
    );

    const editor = useEditor({
      extensions,
      content: resolvedInitial,
      editable: !readOnly,
      onUpdate: ({ editor: e }) => {
        if (onJsonUpdate) {
          const json = e.getJSON();
          contentRef.current = json;
          onJsonUpdate(json);
        }

        if (onHtmlUpdate) {
          onHtmlUpdate(e.getHTML());
        }

        if (onUpdate) {
          const json = contentRef.current || e.getJSON();
          contentRef.current = json;
          onUpdate(json, e.getHTML(), e.getText());
        }
      },
      editorProps: {
        attributes: {
          class: 'tiptap-editor-content focus:outline-none min-h-[800px] text-lg',
          spellcheck: 'false',
        },
        handleDrop: (view, event, _slice, moved) => {
          if (!moved && event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0]) {
            const file = event.dataTransfer.files[0];
            if (/image/i.test(file.type)) {
              handleImageUpload(file, view.state as any);
              return true;
            }
          }
          return false;
        },
        handlePaste: (view, event) => {
          if (event.clipboardData && event.clipboardData.files && event.clipboardData.files[0]) {
            const file = event.clipboardData.files[0];
            if (/image/i.test(file.type)) {
              handleImageUpload(file, view.state as any);
              return true;
            }
          }
          return false;
        },
      },
    });

    const insertTemplate = useCallback(() => {
      if (!editor) return;
      const template = getResearchReportTemplate();
      editor.chain().focus().setContent(template).run();
    }, [editor]);

    const appendToSection = useCallback(
      (sectionId: UniFoliReportSectionId, blocks: ReportContentBlock[]) => {
        if (!editor || !blocks.length) return;
        const nodes = reportContentBlocksToTiptapNodes(blocks);
        const range = findSectionRange(editor, sectionId);
        if (range) {
          editor.chain().focus().insertContentAt(range.contentEnd, nodes).run();
          return;
        }
        // TODO: Replace this heading-text fallback with durable section id nodes/marks.
        editor
          .chain()
          .focus('end')
          .insertContent([paragraphNode(''), { type: 'heading', attrs: { level: 2 }, content: textContent(SECTION_HEADING_LABELS[sectionId]) }, ...nodes])
          .run();
      },
      [editor],
    );

    const replaceSection = useCallback(
      (sectionId: UniFoliReportSectionId, blocks: ReportContentBlock[]) => {
        if (!editor) return;
        const nodes = reportContentBlocksToTiptapNodes(blocks);
        const range = findSectionRange(editor, sectionId);
        if (!range) {
          appendToSection(sectionId, blocks);
          return;
        }
        editor.chain().focus().deleteRange({ from: range.contentStart, to: range.contentEnd }).insertContentAt(range.contentStart, nodes).run();
      },
      [appendToSection, editor],
    );

    const focusSection = useCallback(
      (sectionId: UniFoliReportSectionId) => {
        if (!editor) return;
        const range = findSectionRange(editor, sectionId);
        if (range) {
          editor.chain().focus().setTextSelection(range.headingPos + 1).run();
        }
      },
      [editor],
    );

    const insertMathBlock = useCallback(
      (block: MathContentBlock) => {
        if (!editor) return;
        editor.chain().focus().insertContent(mathBlockToNodes(block)).run();
      },
      [editor],
    );

    const insertFigureBlock = useCallback(
      (block: FigureContentBlock) => {
        if (!editor) return;
        editor.chain().focus().insertContent(figureBlockToNodes(block)).run();
      },
      [editor],
    );

    const updateReferences = useCallback(
      (sources: SourceRecord[]) => {
        if (!editor) return;
        const nodes = sourceRecordsToReferenceNodes(sources);
        const range = findSectionRange(editor, 'references');
        if (range) {
          editor.chain().focus().deleteRange({ from: range.contentStart, to: range.contentEnd }).insertContentAt(range.contentStart, nodes).run();
          return;
        }
        editor
          .chain()
          .focus('end')
          .insertContent([{ type: 'heading', attrs: { level: 2 }, content: textContent(SECTION_HEADING_LABELS.references) }, ...nodes])
          .run();
      },
      [editor],
    );

    const updateCoverMetadata = useCallback(
      (metadata: ReportMetadata) => {
        if (!editor) return;
        const nodes = [
          { type: 'heading', attrs: { level: 1, textAlign: 'center' }, content: textContent(metadata.title || '탐구 보고서') },
          paragraphNode(metadata.subtitle || ''),
          paragraphNode(`학교: ${metadata.schoolName || '____________'}    학년/반: ${metadata.grade || '____'} / ${metadata.className || '____'}`),
          paragraphNode(`이름: ${metadata.studentName || '____________'}    학번: ${metadata.studentId || '____________'}`),
          paragraphNode(`지도교사: ${metadata.teacherName || '____________'}    작성일: ${metadata.date || '____년 __월 __일'}`),
        ];
        const range = findSectionRange(editor, 'cover');
        if (range) {
          editor.chain().focus().deleteRange({ from: range.headingPos, to: range.contentEnd }).insertContentAt(range.headingPos, nodes).run();
          return;
        }
        editor.chain().focus().insertContentAt(0, nodes).run();
      },
      [editor],
    );

    const applyPatch = useCallback(
      (patch: ReportPatch) => {
        if (!editor) return;
        if (patch.requiresApproval && patch.status !== 'accepted' && patch.status !== 'applied') {
          return;
        }
        if (patch.type === 'format') {
          applyFormatPatch(editor, patch, { updateCoverMetadata, updateReferences });
          return;
        }
        applyContentPatch(patch, { appendToSection, replaceSection });
      },
      [appendToSection, editor, replaceSection, updateCoverMetadata, updateReferences],
    );

    const setEditorContent = useCallback(
      (content: JSONContent | string | null) => {
        if (!editor) return;
        const nextContent = typeof content === 'string' ? normalizeInitialStringContent(content) : content || getResearchReportTemplate();
        editor.commands.setContent(nextContent, { emitUpdate: false });
        contentRef.current = editor.getJSON();
      },
      [editor],
    );

    // Expose imperative handle so parent can call getJSON / insertTemplate
    useImperativeHandle(
      ref,
      () => ({
        getJSON: () => contentRef.current || editor?.getJSON() || { type: 'doc', content: [] },
        getHTML: () => editor?.getHTML() || '',
        getMarkdown: () => jsonContentToMarkdown(contentRef.current || editor?.getJSON() || { type: 'doc', content: [] }),
        insertTemplate,
        setContent: setEditorContent,
        applyPatch,
        appendToSection,
        replaceSection,
        focusSection,
        insertMathBlock,
        insertFigureBlock,
        updateCoverMetadata,
        updateReferences,
      }),
      [
        appendToSection,
        applyPatch,
        editor,
        focusSection,
        insertFigureBlock,
        insertMathBlock,
        insertTemplate,
        replaceSection,
        setEditorContent,
        updateCoverMetadata,
        updateReferences,
      ],
    );

    return (
      <div 
        ref={containerRef}
        className="relative flex h-full flex-col overflow-hidden rounded-2xl bg-white shadow-xl ring-1 ring-slate-200 w-full"
      >
        {!readOnly && (
          <div className="flex-none bg-slate-50/50 backdrop-blur-md z-20">
            <EditorToolbar editor={editor} onInsertTemplate={insertTemplate} />
          </div>
        )}

        <div className="flex-1 overflow-auto bg-slate-100/50 p-4 sm:p-10 flex justify-center custom-scrollbar">
          <div 
            className="h-fit transition-all duration-300 origin-top"
          >
            <A4Container scale={zoom / 100}>
              {editor && <EditorContent editor={editor} />}
            </A4Container>
          </div>
        </div>

        {/* Zoom Controls */}
        {!readOnly && (
          <div className="absolute bottom-6 right-6 flex flex-col items-center gap-2 z-30">
             <div className="flex items-center gap-2 rounded-full bg-white/90 p-2 shadow-2xl ring-1 ring-slate-200/50 backdrop-blur-md">
                <button 
                  onClick={() => setZoom(prev => Math.max(30, prev - 10))}
                  className="rounded-full p-2 hover:bg-slate-100 text-slate-500 transition-colors"
                  title="축소"
                >
                  <Minus size={16} />
                </button>
                <div className="px-1 text-[11px] font-black text-slate-600 w-10 text-center tracking-tighter">
                  {zoom}%
                </div>
                <button 
                  onClick={() => setZoom(prev => Math.min(200, prev + 10))}
                  className="rounded-full p-2 hover:bg-slate-100 text-slate-500 transition-colors"
                  title="확대"
                >
                  <Plus size={16} />
                </button>
             </div>
          </div>
        )}
      </div>
    );
  },
);

