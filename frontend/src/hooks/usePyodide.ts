import { useState, useEffect, useRef } from 'react';

declare global {
  interface Window {
    loadPyodide: (config: any) => Promise<any>;
  }
}

export function usePyodide() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pyodideRef = useRef<any>(null);
  const outputRef = useRef<string>('');

  useEffect(() => {
    let isMounted = true;
    const loadEngine = async () => {
      if (window.loadPyodide && pyodideRef.current) {
        if (isMounted) setIsLoading(false);
        return;
      }

      try {
        if (!document.querySelector('#pyodide-script')) {
          const script = document.createElement('script');
          script.id = 'pyodide-script';
          script.src = 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js';
          document.head.appendChild(script);

          await new Promise((resolve, reject) => {
            script.onload = resolve;
            script.onerror = () => reject(new Error('Failed to load Pyodide script.'));
          });
        } else {
          // Wait for script to be fully loaded and expose window.loadPyodide
          while (!window.loadPyodide) {
            await new Promise((r) => setTimeout(r, 100));
          }
        }

        if (!pyodideRef.current) {
          pyodideRef.current = await window.loadPyodide({
            stdout: (msg: string) => {
              outputRef.current += msg + '\n';
            },
            stderr: (msg: string) => {
              outputRef.current += msg + '\n';
            }
          });
        }
        if (isMounted) setIsLoading(false);
      } catch (err: any) {
        if (isMounted) {
          console.error('[Pyodide Load Error]', err);
          setError(err.message || 'Failed to initialize Python engine.');
          setIsLoading(false);
        }
      }
    };

    loadEngine();

    return () => {
      isMounted = false;
    };
  }, []);

  const runPythonCode = async (code: string): Promise<string> => {
    if (!pyodideRef.current) {
      throw new Error('Pyodide 샌드박스가 아직 초기화되지 않았습니다.');
    }

    outputRef.current = ''; // Clear previous output
    try {
      // Auto-load common packages (numpy, pandas, etc.) if imported
      await pyodideRef.current.loadPackagesFromImports(code);
      
      const result = await pyodideRef.current.runPythonAsync(code);
      let finalOutput = outputRef.current;
      
      // If script returns a value but didn't print explicitly, attach it
      if (result !== undefined && finalOutput.trim() === '') {
        finalOutput += String(result);
      }
      
      return finalOutput.trim() || '실행이 완료되었습니다. (출력 결과 없음)';
    } catch (err: any) {
      return `Error:\n${err.message || String(err)}`;
    }
  };

  return { isLoading, error, runPythonCode };
}
