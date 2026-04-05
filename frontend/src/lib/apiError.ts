import axios from 'axios';

function toDetailMessage(detail: unknown): string | null {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => toDetailMessage(item))
      .filter((item): item is string => Boolean(item && item.trim()));
    return parts.length ? parts.join(' | ') : null;
  }
  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    if (typeof record.msg === 'string') return record.msg;
    if (typeof record.message === 'string') return record.message;
    if (typeof record.detail === 'string') return record.detail;
    if (Array.isArray(record.detail)) return toDetailMessage(record.detail);
  }
  return null;
}

export function getApiErrorMessage(error: unknown, fallbackMessage: string): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return '백엔드 서버에 연결할 수 없습니다. API 서버(127.0.0.1:8000)가 실행 중인지 확인해 주세요.';
    }

    const status = error.response.status;
    const detailMessage =
      toDetailMessage(error.response.data) ||
      toDetailMessage((error.response.data as { detail?: unknown } | undefined)?.detail);
    if (detailMessage) return detailMessage;

    if (status === 401) return '인증이 만료되었거나 로그인되지 않았습니다. 다시 로그인해 주세요.';
    if (status === 413) return '파일 용량이 50MB를 초과해 업로드할 수 없습니다.';
    if (status === 429) return '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
    if (status >= 500) return '서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallbackMessage;
}

