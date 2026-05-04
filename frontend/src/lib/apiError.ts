import axios from 'axios';

export interface ApiErrorInfo {
  userMessage: string;
  debugCode: string | null;
  debugDetail: string | null;
  status: number | null;
}

function toDetailMessage(detail: unknown): string | null {
  if (!detail) return null;
  if (typeof detail === 'string') return detail.trim() || null;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => toDetailMessage(item))
      .filter((item): item is string => Boolean(item && item.trim()));
    return parts.length ? parts.join(' | ') : null;
  }
  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    if (typeof record.message === 'string' && record.message.trim()) return record.message.trim();
    if (typeof record.msg === 'string' && record.msg.trim()) return record.msg.trim();
    if (typeof record.debug_detail === 'string' && record.debug_detail.trim()) return record.debug_detail.trim();
    if (typeof record.detail === 'string' && record.detail.trim()) return record.detail.trim();
    if (Array.isArray(record.detail)) return toDetailMessage(record.detail);
    if (record.details) return toDetailMessage(record.details);
  }
  return null;
}

function extractRecord(detail: unknown): Record<string, unknown> | null {
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return detail as Record<string, unknown>;
  }
  return null;
}

function coerceString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized || null;
}

function mapErrorCodeToUserMessage(code: string): string | null {
  switch (code) {
    case 'AUTH_MISSING':
      return '인증 정보가 없습니다. 다시 로그인해 주세요.';
    case 'BACKEND_STARTUP_FAILED':
      return '백엔드 서버가 정상적으로 기동하지 못했습니다. 배포 설정과 DB 연결 상태를 확인해 주세요.';
    case 'DATABASE_URL_REQUIRED':
      return '배포 환경의 DATABASE_URL이 비어 있어 백엔드가 시작되지 못했습니다. 운영자에게 문의해 주세요.';
    case 'DATABASE_UNAVAILABLE':
      return '백엔드가 데이터베이스에 연결하지 못했습니다. DB 접속 정보와 네트워크 설정을 확인해 주세요.';
    case 'PROJECT_NOT_FOUND':
      return '요청한 프로젝트를 찾을 수 없습니다.';
    case 'DOCUMENT_NOT_FOUND':
      return '요청한 문서를 찾을 수 없습니다.';
    case 'FILE_NOT_FOUND':
    case 'FILE_MISSING':
      return '원본 파일을 찾을 수 없습니다. 다시 업로드해 주세요.';
    case 'MALFORMED_PDF':
      return 'PDF 파일이 손상되었거나 형식이 올바르지 않습니다. 다른 파일로 다시 시도해 주세요.';
    case 'ENCRYPTED_PDF':
      return '암호화된 PDF는 바로 분석할 수 없습니다. 암호를 해제한 파일을 업로드해 주세요.';
    case 'NO_USABLE_TEXT':
      return '학생부에서 분석 가능한 텍스트를 충분히 읽지 못했습니다. 더 선명한 PDF로 다시 시도해 주세요.';
    case 'PARSE_TIMEOUT':
      return '문서 분석 시간이 오래 걸려 중단되었습니다. 잠시 후 다시 시도해 주세요.';
    case 'CANONICAL_SCHEMA_EMPTY':
      return '구조화된 학생부 항목을 충분히 만들지 못했습니다. 원문 텍스트 기반 분석으로 다시 시도해 주세요.';
    case 'DIAGNOSIS_INPUT_EMPTY':
      return '진단에 사용할 학생부 내용이 아직 없습니다. 업로드와 파싱을 먼저 완료해 주세요.';
    case 'INVALID_STUDENT_RECORD':
      return '학교생활기록부 원본 PDF만 진단할 수 있습니다. 진단서, 입시 자료, 논문, 일반 PDF가 아니라 나이스/정부24에서 내려받은 학생부 PDF를 업로드해 주세요.';
    case 'DIAGNOSIS_TRACE_PERSIST_FAILED':
      return '진단은 생성되었지만 근거 추적 데이터 저장이 일부 누락되었습니다. 다시 시도하면 복구될 수 있습니다.';
    case 'REPORT_ARTIFACT_FAILED':
      return '진단 결과는 생성되었지만 진단서 아티팩트 저장에 실패했습니다.';
    case 'CHATBOT_CONTEXT_BUILD_FAILED':
      return '챗봇 컨텍스트를 만드는 중 문제가 생겼습니다. 진단 결과 자체는 사용할 수 있습니다.';
    case 'DB_SCHEMA_MISMATCH':
      return '서버 데이터베이스 스키마가 최신 상태가 아닙니다. 운영자에게 마이그레이션 적용을 요청해 주세요.';
    case 'DIAGNOSIS_FAILED':
      return '생기부 진단 생성에 실패했습니다.';
    case 'HTML_MISROUTE':
      return '프런트가 백엔드 API 대신 웹페이지 HTML을 받고 있습니다. VITE_API_URL이 백엔드 주소를 가리키는지, 또는 같은 오리진 배포의 rewrite 설정이 올바른지 확인해 주세요.';
    case 'NETWORK_UNREACHABLE':
      return '백엔드 서버에 연결할 수 없습니다. API 서버 주소, 배포 상태, CORS 설정을 확인해 주세요.';
    case 'GEMINI_API_KEY_MISSING':
      return 'AI 진단에 필요한 Gemini API Key가 설정되지 않았습니다. 관리자 페이지에서 API Key를 입력해 주세요.';
    case 'INTERNAL_ERROR':
      return '서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
    default:
      return null;
  }
}

export function getApiErrorInfo(error: unknown, fallbackMessage: string): ApiErrorInfo {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return {
        userMessage: mapErrorCodeToUserMessage('NETWORK_UNREACHABLE') || '백엔드 서버에 연결할 수 없습니다.',
        debugCode: 'NETWORK_UNREACHABLE',
        debugDetail: error.message || null,
        status: null,
      };
    }

    const status = error.response.status;
    const data = error.response.data as Record<string, unknown> | string | undefined;
    const rootRecord = extractRecord(data);
    const detailRecord = extractRecord(rootRecord?.detail);
    const responseHeaders = error.response.headers as Record<string, unknown> | undefined;
    const responseText = typeof data === 'string' ? data : null;
    const vercelError = coerceString(responseHeaders?.['x-vercel-error']);

    let debugCode =
      coerceString(rootRecord?.code) ||
      coerceString(rootRecord?.error_code) ||
      coerceString(detailRecord?.code) ||
      coerceString(detailRecord?.error_code);

    if (!debugCode && (vercelError === 'FUNCTION_INVOCATION_FAILED' || responseText?.includes('FUNCTION_INVOCATION_FAILED'))) {
      debugCode = 'BACKEND_STARTUP_FAILED';
    }

    if (!debugCode && String(responseHeaders?.['content-type'] || '').toLowerCase().includes('text/html')) {
      debugCode = 'HTML_MISROUTE';
    }

    const detailMessage =
      toDetailMessage(detailRecord) ||
      toDetailMessage(rootRecord?.detail) ||
      toDetailMessage(rootRecord) ||
      toDetailMessage(data);
    const debugDetail =
      coerceString(detailRecord?.debug_detail) ||
      coerceString(rootRecord?.debug_detail) ||
      vercelError ||
      detailMessage;
    const mappedMessage = debugCode ? mapErrorCodeToUserMessage(debugCode) : null;

    if (mappedMessage) {
      return {
        userMessage: mappedMessage,
        debugCode,
        debugDetail,
        status,
      };
    }

    if (detailMessage) {
      return {
        userMessage: detailMessage,
        debugCode,
        debugDetail,
        status,
      };
    }

    if (status === 401) {
      return {
        userMessage: '인증이 만료되었거나 로그인이 필요합니다. 다시 로그인해 주세요.',
        debugCode,
        debugDetail,
        status,
      };
    }
    if (status === 413) {
      return {
        userMessage: '파일 용량이 너무 큽니다. 더 작은 PDF로 다시 시도해 주세요.',
        debugCode,
        debugDetail,
        status,
      };
    }
    if (status === 429) {
      return {
        userMessage: '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
        debugCode,
        debugDetail,
        status,
      };
    }
    if (status >= 500) {
      return {
        userMessage: '서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        debugCode,
        debugDetail,
        status,
      };
    }

    return {
      userMessage: fallbackMessage,
      debugCode,
      debugDetail,
      status,
    };
  }

  if (error instanceof Error) {
    if (error.message.includes('Backend API is returning HTML') || (error as any).debugCode === 'HTML_MISROUTE') {
      return {
        userMessage: mapErrorCodeToUserMessage('HTML_MISROUTE') || '프런트가 백엔드 대신 HTML을 받고 있습니다.',
        debugCode: 'HTML_MISROUTE',
        debugDetail: error.message,
        status: (error as any).status || null,
      };
    }
    const message = error.message.trim();
    return {
      userMessage: message || fallbackMessage,
      debugCode: null,
      debugDetail: message || null,
      status: null,
    };
  }

  return {
    userMessage: fallbackMessage,
    debugCode: null,
    debugDetail: null,
    status: null,
  };
}

export function getApiErrorMessage(error: unknown, fallbackMessage: string): string {
  return getApiErrorInfo(error, fallbackMessage).userMessage;
}
