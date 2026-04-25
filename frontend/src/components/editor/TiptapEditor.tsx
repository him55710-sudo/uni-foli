import React, { useCallback, useRef, useMemo, useImperativeHandle, forwardRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import type { JSONContent } from '@tiptap/react';
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

import { FontSize } from './extensions/FontSize';
import { LineHeight } from './extensions/LineHeight';
import { EditorToolbar } from './EditorToolbar';
import { A4Container } from './A4Container';
import { getResearchReportTemplate } from './templates/researchReport';

import './TiptapEditor.css';

export interface TiptapEditorHandle {
  getJSON: () => JSONContent;
  getHTML: () => string;
  insertTemplate: () => void;
  setContent: (content: any) => void;
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
          class: 'tiptap-editor-content focus:outline-none',
          spellcheck: 'false',
        },
      },
    });

    const insertTemplate = useCallback(() => {
      if (!editor) return;
      const template = getResearchReportTemplate();
      editor.chain().focus().setContent(template).run();
    }, [editor]);

    // Expose imperative handle so parent can call getJSON / insertTemplate
    useImperativeHandle(
      ref,
      () => ({
        getJSON: () => contentRef.current || editor?.getJSON() || { type: 'doc', content: [] },
        getHTML: () => editor?.getHTML() || '',
        insertTemplate,
        setContent: (content: any) => editor?.commands.setContent(content),
      }),
      [editor, insertTemplate],
    );

    return (
      <div className="flex h-full w-full flex-col overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/80">
        {!readOnly && <EditorToolbar editor={editor} onInsertTemplate={insertTemplate} />}

        <div className="flex-1 overflow-y-auto">
          <A4Container>
            {editor && <EditorContent editor={editor} />}
          </A4Container>
        </div>
      </div>
    );
  },
);
