import { useMemo, useState, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FileImage,
  FlaskConical,
  GitBranch,
  Sigma,
  Table2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const ChartComponent = lazy(() => import('./ChartComponent').then((m) => ({ default: m.ChartComponent })));

interface ChartSpec {
  title: string;
  type: 'bar' | 'line';
  unit?: string;
  data: { name: string; value: number }[];
}

interface TableSpec {
  columns: string[];
  rows: string[][];
}

interface DiagramSpec {
  layout?: string;
  steps: string[];
}

interface EquationSpec {
  label?: string;
  latex: string;
}

interface ImageSpec {
  image_url?: string;
  alt_text?: string;
  thumbnail_url?: string;
}

interface VisualProvenance {
  kind?: string;
  source_url?: string | null;
  source_title?: string | null;
  source_type?: string | null;
  trust_note?: string | null;
  why_selected?: string | null;
  supported_section?: string | null;
  basis?: string[];
  basis_provenance?: string[];
  evidence_refs?: string[];
}

interface VisualSpec {
  id?: string;
  type: string;
  title?: string;
  caption?: string;
  confidence?: number;
  rationale?: string;
  origin?: string;
  approval_status?: 'proposed' | 'approved' | 'rejected' | 'replaced' | 'removed';
  section_title?: string;
  chart_spec?: ChartSpec;
  table_spec?: TableSpec;
  diagram_spec?: DiagramSpec;
  equation_spec?: EquationSpec;
  image_spec?: ImageSpec;
  provenance?: VisualProvenance;
}

interface MathExpression {
  id?: string;
  label: string;
  latex: string;
  context?: string;
  approval_status?: string;
}

interface AdvancedPreviewProps {
  workshopId: string;
  artifactId: string;
  visualSpecs: VisualSpec[];
  mathExpressions: MathExpression[];
  isAdvancedMode: boolean;
  onUpdateVisualStatus?: (visualId: string, status: string) => void;
}

export function AdvancedPreview({
  workshopId,
  artifactId,
  visualSpecs,
  mathExpressions,
  isAdvancedMode,
  onUpdateVisualStatus,
}: AdvancedPreviewProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const normalizedVisuals = useMemo<VisualSpec[]>(() => {
    const existingEquationLatex = new Set(
      visualSpecs
        .filter((spec) => spec.type === 'equation' && spec.equation_spec?.latex)
        .map((spec) => spec.equation_spec!.latex),
    );

    const legacyEquations = mathExpressions
      .filter((expr) => expr.latex && !existingEquationLatex.has(expr.latex))
      .map<VisualSpec>((expr, index) => ({
        id: expr.id || `legacy-math-${index}`,
        type: 'equation',
        title: expr.label,
        caption: expr.context || 'Legacy math block kept for preview compatibility.',
        confidence: 0.7,
        rationale: expr.context || 'Kept as a formula block from the render artifact.',
        origin: 'generated',
        approval_status: (expr.approval_status as any) || 'proposed',
        equation_spec: {
          label: expr.label,
          latex: expr.latex,
        },
        provenance: {
          kind: 'generated',
          source_type: 'legacy_math_expression',
          trust_note: 'This formula block came from the render artifact and should be reviewed with the section text.',
        },
      }));

    return [...visualSpecs, ...legacyEquations];
  }, [mathExpressions, visualSpecs]);

  if (!isAdvancedMode || normalizedVisuals.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, type: 'spring', bounce: 0.18 }}
      className="mx-auto mt-6 max-w-[210mm]"
    >
      <div className="overflow-hidden rounded-3xl border border-indigo-500/30 bg-gradient-to-br from-slate-900 via-indigo-950/60 to-slate-900 shadow-xl shadow-indigo-500/5">
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="flex w-full items-center justify-between px-6 py-4 transition-colors hover:bg-white/5"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-300">
              <FlaskConical size={16} />
            </div>
            <div className="text-left">
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-indigo-400">
                Visual Support Proposals
              </p>
              <p className="mt-0.5 text-xs font-medium text-slate-400">
                Review and approve context-aware visuals for your report.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-extrabold text-indigo-300">
              {normalizedVisuals.length} items
            </span>
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </button>

        <AnimatePresence mode="popLayout">
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.28 }}
              className="overflow-hidden"
            >
              <div className="space-y-4 px-6 pb-6">
                {normalizedVisuals.map((spec) => (
                  <VisualCard
                    key={spec.id || `${spec.type}-${spec.title}`}
                    spec={spec}
                    onStatusChange={(status) => spec.id && onUpdateVisualStatus?.(spec.id, status)}
                  />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function VisualCard({ spec, onStatusChange }: { spec: VisualSpec; onStatusChange: (status: string) => void }) {
  const confidence = typeof spec.confidence === 'number' ? spec.confidence : 0;
  const status = spec.approval_status || 'proposed';

  const confidenceLabel = confidence >= 0.85 ? 'High confidence' : confidence >= 0.72 ? 'Reviewable' : 'Low confidence';
  const confidenceTone =
    confidence >= 0.85
      ? 'bg-emerald-500/10 text-emerald-300'
      : confidence >= 0.72
        ? 'bg-amber-500/10 text-amber-200'
        : 'bg-rose-500/10 text-rose-200';

  const statusTone = {
    proposed: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20',
    approved: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    rejected: 'bg-slate-700/40 text-slate-400 border-slate-700/50 grayscale',
    replaced: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
    removed: 'bg-rose-500/10 text-rose-300 border-rose-500/20 opacity-50',
  }[status];

  return (
    <div
      className={`overflow-hidden rounded-2xl border transition-all duration-300 ${status === 'rejected' ? 'border-slate-800 bg-slate-900/40' : 'border-slate-700/50 bg-slate-800/65'}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/60 px-5 py-4">
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-300">
              {labelForType(spec.type)}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] ${statusTone}`}
            >
              {status}
            </span>
            {status === 'proposed' && (
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] ${confidenceTone}`}
              >
                {confidenceLabel}
              </span>
            )}
            <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.16em] text-indigo-200">
              {spec.origin === 'external_source' ? 'External source' : 'Generated visual'}
            </span>
          </div>
          <p className="mt-2 text-sm font-extrabold text-slate-100">{spec.title || 'Untitled visual support'}</p>
          {spec.section_title && (
            <p className="mt-1 text-xs font-medium text-slate-400">Supports section: {spec.section_title}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {typeof spec.confidence === 'number' && (
            <span className="text-xs font-bold text-slate-400">{Math.round(spec.confidence * 100)}% Match</span>
          )}
        </div>
      </div>

      <div className={`space-y-4 p-5 ${status === 'rejected' ? 'opacity-40 blur-[1px]' : ''}`}>
        <VisualBody spec={spec} />

        {(spec.caption || spec.rationale) && (
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/50 p-4">
            {spec.caption && <p className="text-sm font-semibold leading-relaxed text-slate-200">{spec.caption}</p>}
            {spec.rationale && (
              <div className="mt-2 flex items-start gap-2">
                <span className="mt-0.5 rounded bg-amber-500/10 px-1 py-0.5 text-[8px] font-black text-amber-200">
                  RATIONALE
                </span>
                <p className="text-xs font-medium leading-relaxed text-slate-400">{spec.rationale}</p>
              </div>
            )}
          </div>
        )}

        {spec.provenance && <ProvenanceNote provenance={spec.provenance} />}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-slate-700/60 bg-slate-900/30 px-5 py-3">
        {status !== 'approved' && (
          <button
            onClick={() => onStatusChange('approved')}
            className="flex items-center gap-1.5 rounded-xl bg-emerald-600/20 px-3 py-1.5 text-xs font-black text-emerald-300 transition-colors hover:bg-emerald-600/30"
          >
            Approve & Keep
          </button>
        )}
        {status === 'approved' && (
          <button
            onClick={() => onStatusChange('proposed')}
            className="flex items-center gap-1.5 rounded-xl bg-slate-700/40 px-3 py-1.5 text-xs font-black text-slate-300 transition-colors hover:bg-slate-700/60"
          >
            Undo Approval
          </button>
        )}
        {status !== 'rejected' && (
          <button
            onClick={() => onStatusChange('rejected')}
            className="flex items-center gap-1.5 rounded-xl bg-rose-600/10 px-3 py-1.5 text-xs font-black text-rose-300 transition-colors hover:bg-rose-600/20"
          >
            Reject
          </button>
        )}
        {status === 'rejected' && (
          <button
            onClick={() => onStatusChange('proposed')}
            className="flex items-center gap-1.5 rounded-xl bg-slate-700/40 px-3 py-1.5 text-xs font-black text-slate-300 transition-colors hover:bg-slate-700/60"
          >
            Restore
          </button>
        )}
        <button
          onClick={() => onStatusChange('replaced')}
          className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-transparent px-3 py-1.5 text-xs font-black text-slate-400 transition-colors hover:bg-white/5 hover:text-slate-200"
        >
          Replace Visual
        </button>
      </div>
    </div>
  );
}

function VisualBody({ spec }: { spec: VisualSpec }) {
  if (spec.type === 'chart' && spec.chart_spec) {
    return (
      <Suspense
        fallback={
          <div className="rounded-2xl bg-slate-900/50 p-4 text-center text-xs text-slate-400">Loading chart...</div>
        }
      >
        <ChartComponent jsonString={JSON.stringify(spec.chart_spec)} />
      </Suspense>
    );
  }

  if (spec.type === 'table' && spec.table_spec) {
    return (
      <div className="overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/40">
        <div className="flex items-center gap-2 border-b border-slate-700/60 px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
          <Table2 size={12} />
          Comparison Table
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm text-slate-100">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-400">
              <tr>
                {spec.table_spec.columns.map((column) => (
                  <th key={column} className="px-4 py-3 font-black">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spec.table_spec.rows.map((row, rowIndex) => (
                <tr key={`${spec.id}-row-${rowIndex}`} className="border-t border-slate-700/40">
                  {row.map((cell, cellIndex) => (
                    <td
                      key={`${spec.id}-cell-${rowIndex}-${cellIndex}`}
                      className="px-4 py-3 align-top text-sm font-medium text-slate-200"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (spec.type === 'diagram' && spec.diagram_spec) {
    return (
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
        <div className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
          <GitBranch size={12} />
          Flow Diagram
        </div>
        <div className="space-y-3">
          {spec.diagram_spec.steps.map((step, index) => (
            <div key={`${spec.id}-step-${index}`} className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-500/15 text-xs font-black text-indigo-200">
                {index + 1}
              </div>
              <div className="flex-1 rounded-2xl border border-slate-700/60 bg-white/5 px-4 py-3 text-sm font-medium leading-relaxed text-slate-100">
                {step}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (spec.type === 'equation' && spec.equation_spec?.latex) {
    return (
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
        <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
          <Sigma size={12} />
          Formula Block
        </div>
        <div className="rounded-2xl bg-slate-950/80 px-4 py-4 text-sm text-slate-100">
          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
            {`$$${spec.equation_spec.latex}$$`}
          </ReactMarkdown>
        </div>
      </div>
    );
  }

  if (spec.type === 'external_image' && spec.image_spec) {
    return (
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
        <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
          <FileImage size={12} />
          External Visual
        </div>
        {spec.image_spec.image_url ? (
          <div className="overflow-hidden rounded-2xl border border-slate-700/60 bg-black/20">
            <img
              src={spec.image_spec.thumbnail_url || spec.image_spec.image_url}
              alt={spec.image_spec.alt_text || spec.title || 'External visual support'}
              className="max-h-80 w-full object-cover"
            />
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-700/70 px-4 py-6 text-center text-sm font-medium text-slate-400">
            External visual selected, but no preview URL is available in this environment.
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-slate-700/70 px-4 py-6 text-center text-sm font-medium text-slate-400">
      No renderable preview payload was stored for this visual block.
    </div>
  );
}

function ProvenanceNote({ provenance }: { provenance: VisualProvenance }) {
  const basis = provenance.basis || [];
  const basisTypes = provenance.basis_provenance || [];
  const evidenceRefs = provenance.evidence_refs || [];

  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-950/60 p-4">
      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Provenance / Evidence</p>
      <div className="mt-3 space-y-2 text-xs font-medium leading-relaxed text-slate-300">
        {provenance.why_selected && <p>{provenance.why_selected}</p>}
        {provenance.trust_note && <p className="text-slate-400">{provenance.trust_note}</p>}
        {provenance.source_title && <p>Source title: {provenance.source_title}</p>}
        {provenance.supported_section && <p>Supported section: {provenance.supported_section}</p>}
        {provenance.source_url && (
          <a
            href={provenance.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-bold text-indigo-300 hover:text-indigo-200"
          >
            Open source
            <ExternalLink size={12} />
          </a>
        )}
      </div>

      {(basis.length > 0 || basisTypes.length > 0 || evidenceRefs.length > 0) && (
        <div className="mt-4 border-t border-white/5 pt-4">
          <p className="mb-2 text-[9px] font-black uppercase tracking-[0.1em] text-slate-500">Grounded in:</p>
          <div className="flex flex-wrap gap-2">
            {basis.map((item) => (
              <span
                key={`basis-${item}`}
                className="rounded-full bg-white/5 px-2 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-300"
              >
                {item}
              </span>
            ))}
            {basisTypes.map((item) => (
              <span
                key={`type-${item}`}
                className="rounded-full bg-indigo-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-indigo-200"
              >
                {item}
              </span>
            ))}
            {evidenceRefs.map((item) => (
              <span
                key={`ref-${item}`}
                className="rounded-full bg-emerald-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-emerald-200"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function labelForType(type: string) {
  switch (type) {
    case 'chart':
      return 'Chart';
    case 'table':
      return 'Table';
    case 'diagram':
      return 'Diagram';
    case 'equation':
      return 'Equation';
    case 'external_image':
      return 'Image';
    default:
      return 'Visual';
  }
}
