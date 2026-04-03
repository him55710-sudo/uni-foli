import React, { useCallback, useRef, useState } from 'react';
import { type Editor } from '@tiptap/react';
import {
  Bold,
  Italic,
  Underline,
  Strikethrough,
  List,
  ListOrdered,
  Quote,
  Undo,
  Redo,
  AlignCenter,
  AlignLeft,
  AlignRight,
  AlignJustify,
  Heading1,
  Heading2,
  Heading3,
  Table as TableIcon,
  Columns,
  Rows,
  Trash2,
  Image as ImageIcon,
  Link as LinkIcon,
  CheckSquare,
  Highlighter,
  PaintbrushVertical,
  FileDown,
  Minus,
  Plus,
} from 'lucide-react';
import { cn } from '../../lib/cn';

interface EditorToolbarProps {
  editor: Editor | null;
  onInsertTemplate?: () => void;
}

const FONT_FAMILIES = [
  { label: '기본 (Pretendard)', value: 'Pretendard' },
  { label: 'Noto Sans KR', value: 'Noto Sans KR' },
  { label: '나눔고딕', value: 'NanumGothic' },
  { label: 'Roboto', value: 'Roboto' },
  { label: 'Inter', value: 'Inter' },
  { label: 'Georgia', value: 'Georgia' },
  { label: 'Times New Roman', value: 'Times New Roman' },
];

const FONT_SIZES = [
  { label: '10', value: '10px' },
  { label: '11', value: '11px' },
  { label: '12', value: '12px' },
  { label: '14', value: '14px' },
  { label: '16', value: '16px' },
  { label: '18', value: '18px' },
  { label: '20', value: '20px' },
  { label: '24', value: '24px' },
  { label: '28', value: '28px' },
  { label: '32', value: '32px' },
  { label: '36', value: '36px' },
  { label: '48', value: '48px' },
];

const LINE_HEIGHTS = [
  { label: '1.0', value: '1' },
  { label: '1.15', value: '1.15' },
  { label: '1.5', value: '1.5' },
  { label: '1.75', value: '1.75' },
  { label: '2.0', value: '2' },
  { label: '2.5', value: '2.5' },
  { label: '3.0', value: '3' },
];

const PRESET_COLORS = [
  '#000000', '#434343', '#666666', '#999999', '#cccccc',
  '#1a73e8', '#1967d2', '#0d47a1', '#4285f4', '#8ab4f8',
  '#0b8043', '#137333', '#1e8e3e', '#34a853', '#81c995',
  '#ea4335', '#c5221f', '#b31412', '#d93025', '#f28b82',
  '#f9ab00', '#e37400', '#e8710a', '#fbbc04', '#fdd663',
  '#9334e6', '#7627bb', '#681da8', '#a142f4', '#d7aefb',
];

function ToolbarButton({
  onClick,
  active = false,
  disabled = false,
  children,
  title,
  className,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 sm:h-7 sm:w-7 disabled:pointer-events-none disabled:opacity-30',
        active && 'bg-blue-100 text-blue-700 hover:bg-blue-100',
        className,
      )}
    >
      {children}
    </button>
  );
}

function ToolbarDivider() {
  return <div className="mx-0.5 h-5 w-px shrink-0 bg-slate-200" />;
}

function ColorPicker({
  currentColor,
  onSelect,
  title,
  icon,
}: {
  currentColor: string;
  onSelect: (color: string) => void;
  title: string;
  icon: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => setIsOpen(!isOpen)}
        title={title}
        className="flex h-8 w-8 flex-col items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 sm:h-7 sm:w-7"
      >
        {icon}
        <div className="mt-0.5 h-[3px] w-4 rounded-full" style={{ backgroundColor: currentColor || '#000' }} />
      </button>
      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 w-[180px] rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
            <div className="grid grid-cols-5 gap-1">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  className={cn(
                    'h-6 w-6 rounded-md border border-slate-200 transition-transform hover:scale-110',
                    currentColor === color && 'ring-2 ring-blue-500 ring-offset-1',
                  )}
                  style={{ backgroundColor: color }}
                  onClick={() => {
                    onSelect(color);
                    setIsOpen(false);
                  }}
                />
              ))}
            </div>
            <div className="mt-2 flex items-center gap-1 border-t border-slate-100 pt-2">
              <input
                type="color"
                className="h-6 w-6 cursor-pointer rounded border-none bg-transparent"
                value={currentColor || '#000000'}
                onChange={(e) => {
                  onSelect(e.target.value);
                  setIsOpen(false);
                }}
              />
              <span className="text-[10px] text-slate-400">커스텀</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export function EditorToolbar({ editor, onInsertTemplate }: EditorToolbarProps) {
  if (!editor) return null;

  const currentFontSize = editor.getAttributes('textStyle').fontSize || '16px';
  const currentFontFamily = editor.getAttributes('textStyle').fontFamily || 'Pretendard';
  const currentLineHeight = editor.getAttributes('paragraph').lineHeight || '1.6';
  const currentColor = editor.getAttributes('textStyle').color || '#000000';

  const addImage = useCallback(() => {
    const url = window.prompt('이미지 URL을 입력하세요');
    if (url) {
      editor.chain().focus().setImage({ src: url }).run();
    }
  }, [editor]);

  const setLink = useCallback(() => {
    const previousUrl = editor.getAttributes('link').href;
    const url = window.prompt('링크 URL을 입력하세요', previousUrl);
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  }, [editor]);

  return (
    <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-sm">
      {/* Row 1: Primary formatting */}
      <div className="flex items-center gap-0.5 overflow-x-auto px-2 py-1.5 sm:px-3 [&::-webkit-scrollbar]:h-0">
        {/* Undo / Redo */}
        <ToolbarButton onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title="실행 취소 (Ctrl+Z)">
          <Undo size={15} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title="다시 실행 (Ctrl+Y)">
          <Redo size={15} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Font Family */}
        <select
          className="h-7 rounded-md border border-slate-200 bg-transparent px-1.5 text-[11px] font-semibold text-slate-700 outline-none hover:bg-slate-50 focus:ring-1 focus:ring-blue-300"
          value={currentFontFamily}
          onChange={(e) => editor.chain().focus().setFontFamily(e.target.value).run()}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {FONT_FAMILIES.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>

        {/* Font Size */}
        <select
          className="h-7 w-14 rounded-md border border-slate-200 bg-transparent px-1 text-[11px] font-semibold text-slate-700 outline-none hover:bg-slate-50 focus:ring-1 focus:ring-blue-300"
          value={currentFontSize}
          onChange={(e) => editor.chain().focus().setFontSize(e.target.value).run()}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {FONT_SIZES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>

        <ToolbarDivider />

        {/* Bold / Italic / Underline / Strikethrough */}
        <ToolbarButton active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title="굵게 (Ctrl+B)">
          <Bold size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title="기울임 (Ctrl+I)">
          <Italic size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title="밑줄 (Ctrl+U)">
          <Underline size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} title="취소선">
          <Strikethrough size={15} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Text Color */}
        <ColorPicker
          currentColor={currentColor}
          onSelect={(color) => editor.chain().focus().setColor(color).run()}
          title="글자 색"
          icon={<PaintbrushVertical size={14} />}
        />

        {/* Highlight / Background Color */}
        <ColorPicker
          currentColor={editor.getAttributes('highlight').color || '#fdd663'}
          onSelect={(color) => editor.chain().focus().toggleHighlight({ color }).run()}
          title="배경 색"
          icon={<Highlighter size={14} />}
        />

        <ToolbarDivider />

        {/* Headings */}
        <ToolbarButton active={editor.isActive('heading', { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} title="제목 1">
          <Heading1 size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('heading', { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} title="제목 2">
          <Heading2 size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('heading', { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} title="제목 3">
          <Heading3 size={15} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Alignment */}
        <ToolbarButton active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} title="왼쪽 정렬">
          <AlignLeft size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} title="가운데 정렬">
          <AlignCenter size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} title="오른쪽 정렬">
          <AlignRight size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive({ textAlign: 'justify' })} onClick={() => editor.chain().focus().setTextAlign('justify').run()} title="양쪽 맞춤">
          <AlignJustify size={15} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Line Height */}
        <select
          className="h-7 w-14 rounded-md border border-slate-200 bg-transparent px-1 text-[11px] font-semibold text-slate-700 outline-none hover:bg-slate-50 focus:ring-1 focus:ring-blue-300"
          value={currentLineHeight}
          title="줄 간격"
          onChange={(e) => editor.chain().focus().setLineHeight(e.target.value).run()}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {LINE_HEIGHTS.map((lh) => (
            <option key={lh.value} value={lh.value}>↕ {lh.label}</option>
          ))}
        </select>

        <ToolbarDivider />

        {/* Lists */}
        <ToolbarButton active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} title="글머리 기호">
          <List size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="번호 매기기">
          <ListOrdered size={15} />
        </ToolbarButton>
        <ToolbarButton active={editor.isActive('taskList')} onClick={() => editor.chain().focus().toggleTaskList().run()} title="체크리스트">
          <CheckSquare size={15} />
        </ToolbarButton>

        {/* Blockquote */}
        <ToolbarButton active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()} title="인용구">
          <Quote size={15} />
        </ToolbarButton>

        {/* Horizontal Rule */}
        <ToolbarButton onClick={() => editor.chain().focus().setHorizontalRule().run()} title="구분선">
          <Minus size={15} />
        </ToolbarButton>

        <ToolbarDivider />

        {/* Link / Image / Table */}
        <ToolbarButton active={editor.isActive('link')} onClick={setLink} title="링크 삽입">
          <LinkIcon size={15} />
        </ToolbarButton>
        <ToolbarButton onClick={addImage} title="이미지 삽입">
          <ImageIcon size={15} />
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
          title="표 삽입"
        >
          <TableIcon size={15} />
        </ToolbarButton>

        {/* Template insert */}
        {onInsertTemplate && (
          <>
            <ToolbarDivider />
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={onInsertTemplate}
              className="flex h-7 items-center gap-1 rounded-md bg-blue-50 px-2 text-[11px] font-bold text-blue-700 transition-colors hover:bg-blue-100"
              title="탐구보고서 템플릿 삽입"
            >
              <FileDown size={13} />
              템플릿
            </button>
          </>
        )}
      </div>

      {/* Row 2: Table controls (conditional) */}
      {editor.isActive('table') && (
        <div className="flex items-center gap-0.5 border-t border-slate-100 bg-blue-50/40 px-3 py-1">
          <span className="mr-1 text-[10px] font-bold text-blue-600">표 편집</span>
          <ToolbarButton onClick={() => editor.chain().focus().addColumnBefore().run()} title="왼쪽에 열 추가">
            <Plus size={13} />
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().addColumnAfter().run()} title="오른쪽에 열 추가">
            <Columns size={13} />
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().deleteColumn().run()} title="열 삭제">
            <Trash2 size={13} className="text-red-500" />
          </ToolbarButton>
          <ToolbarDivider />
          <ToolbarButton onClick={() => editor.chain().focus().addRowBefore().run()} title="위에 행 추가">
            <Plus size={13} />
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().addRowAfter().run()} title="아래에 행 추가">
            <Rows size={13} />
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().deleteRow().run()} title="행 삭제">
            <Trash2 size={13} className="text-red-500" />
          </ToolbarButton>
          <ToolbarDivider />
          <ToolbarButton onClick={() => editor.chain().focus().toggleHeaderRow().run()} title="머리글 행 전환">
            <Heading1 size={13} />
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().mergeCells().run()} title="셀 병합">
            <span className="text-[10px] font-bold">병합</span>
          </ToolbarButton>
          <ToolbarButton onClick={() => editor.chain().focus().splitCell().run()} title="셀 분할">
            <span className="text-[10px] font-bold">분할</span>
          </ToolbarButton>
          <ToolbarDivider />
          <ToolbarButton onClick={() => editor.chain().focus().deleteTable().run()} title="표 삭제" className="text-red-600 hover:bg-red-50">
            <Trash2 size={13} />
          </ToolbarButton>
        </div>
      )}
    </div>
  );
}
