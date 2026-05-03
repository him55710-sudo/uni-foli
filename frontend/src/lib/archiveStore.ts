export interface ArchiveItem {
  id: string;
  projectId: string | null;
  workshopId?: string | null;
  kind?: 'report' | 'workshop';
  title: string;
  subject: string;
  createdAt: string;
  updatedAt?: string;
  contentMarkdown: string;
  structuredDraft?: unknown;
  chatMessages?: Array<{
    id: string;
    role: 'user' | 'foli';
    content: string;
    createdAt?: string;
  }>;
}

const STORAGE_KEY = 'uni_foli_archive_items';

function readItems(): ArchiveItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ArchiveItem[];
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function writeItems(items: ArchiveItem[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

export function listArchiveItems(): ArchiveItem[] {
  return readItems().sort((a, b) => ((a.updatedAt || a.createdAt) < (b.updatedAt || b.createdAt) ? 1 : -1));
}

export function getArchiveItem(id: string): ArchiveItem | null {
  return readItems().find((item) => item.id === id) ?? null;
}

export function saveArchiveItem(item: ArchiveItem): void {
  const items = readItems();
  const previous = items.find((entry) => entry.id === item.id);
  const merged: ArchiveItem = {
    ...previous,
    ...item,
    createdAt: previous?.createdAt || item.createdAt,
    updatedAt: item.updatedAt || new Date().toISOString(),
  };
  const next = [merged, ...items.filter((entry) => entry.id !== item.id)].slice(0, 100);
  writeItems(next);
}

export function downloadArchiveAsText(item: ArchiveItem, format: 'hwpx' | 'pdf'): void {
  const header = [
    `# ${item.title}`,
    '',
    `- Subject: ${item.subject}`,
    `- Created: ${new Date(item.createdAt).toLocaleString()}`,
    item.projectId ? `- Project ID: ${item.projectId}` : '- Project ID: local',
    '',
  ].join('\n');

  const payload = `${header}${item.contentMarkdown || ''}`.trim();
  const blob = new Blob([payload], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${item.title.replace(/[^\w\-\uAC00-\uD7A3]+/g, '_')}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
export function deleteArchiveItem(id: string): void {
  const items = readItems();
  const next = items.filter((item) => item.id !== id);
  writeItems(next);
}
