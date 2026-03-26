const CHOSEONG = [
  'ㄱ',
  'ㄲ',
  'ㄴ',
  'ㄷ',
  'ㄸ',
  'ㄹ',
  'ㅁ',
  'ㅂ',
  'ㅃ',
  'ㅅ',
  'ㅆ',
  'ㅇ',
  'ㅈ',
  'ㅉ',
  'ㅊ',
  'ㅋ',
  'ㅌ',
  'ㅍ',
  'ㅎ',
] as const;

const CHOSEONG_SET = new Set<string>(CHOSEONG);
const HANGUL_START = 0xac00;
const HANGUL_END = 0xd7a3;
const CHOSEONG_INTERVAL = 588;

export function normalizeSearchText(value: string): string {
  return value
    .normalize('NFC')
    .toLowerCase()
    .replace(/[\s\-_/()[\]{}.,]+/g, '');
}

export function extractInitialConsonants(value: string): string {
  let result = '';

  for (const char of value.normalize('NFC')) {
    const code = char.charCodeAt(0);
    if (code >= HANGUL_START && code <= HANGUL_END) {
      result += CHOSEONG[Math.floor((code - HANGUL_START) / CHOSEONG_INTERVAL)];
      continue;
    }

    if (CHOSEONG_SET.has(char) || /[a-z0-9]/i.test(char)) {
      result += char.toLowerCase();
    }
  }

  return result;
}

export function isChoseongQuery(value: string): boolean {
  const normalized = normalizeSearchText(value);
  return normalized.length > 0 && [...normalized].every((char) => CHOSEONG_SET.has(char));
}
