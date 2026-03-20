export interface ArchiveItem {
  id: string;
  projectId: string | null;
  title: string;
  subject: string;
  createdAt: string;
  contentMarkdown: string;
}

const STORAGE_KEY = 'polio_archive_items';

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
  return readItems().sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

export function saveArchiveItem(item: ArchiveItem): void {
  const items = readItems();
  const next = [item, ...items.filter((entry) => entry.id !== item.id)].slice(0, 100);
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
