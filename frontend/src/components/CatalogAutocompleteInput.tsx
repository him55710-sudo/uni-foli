import React, { useState } from 'react';
import type { CatalogSuggestion } from '../lib/educationCatalog';

interface CatalogAutocompleteInputProps {
  label: string;
  value: string;
  placeholder: string;
  suggestions: CatalogSuggestion[];
  onChange: (value: string) => void;
  onSelect: (suggestion: CatalogSuggestion) => void;
  helperText?: string;
  emptyText?: string;
  disabled?: boolean;
  autoFocus?: boolean;
}

export function CatalogAutocompleteInput({
  label,
  value,
  placeholder,
  suggestions,
  onChange,
  onSelect,
  helperText,
  emptyText,
  disabled = false,
  autoFocus = false,
}: CatalogAutocompleteInputProps) {
  const [isOpen, setIsOpen] = useState(false);
  const shouldShowPanel = isOpen && (suggestions.length > 0 || (value.trim().length > 0 && emptyText));

  return (
    <div className="relative">
      <label className="mb-3 block text-sm font-extrabold text-slate-700">{label}</label>
      <input
        type="text"
        value={value}
        disabled={disabled}
        autoFocus={autoFocus}
        placeholder={placeholder}
        onFocus={() => setIsOpen(true)}
        onBlur={() => {
          window.setTimeout(() => setIsOpen(false), 120);
        }}
        onChange={(event) => {
          onChange(event.target.value);
          setIsOpen(true);
        }}
        className="w-full rounded-3xl border-2 border-slate-100 bg-slate-50 px-5 py-4 text-lg font-bold text-slate-800 shadow-sm outline-none transition-all placeholder:text-slate-300 focus:border-blue-400 focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
      />
      {helperText ? (
        <p className="mt-2 text-xs font-medium leading-relaxed text-slate-500">{helperText}</p>
      ) : null}
      {shouldShowPanel ? (
        <div className="absolute left-0 right-0 z-30 mt-3 max-h-72 overflow-y-auto rounded-3xl border border-slate-200 bg-white p-2 shadow-2xl">
          {suggestions.length ? (
            suggestions.map((suggestion) => (
              <button
                key={suggestion.id}
                type="button"
                onMouseDown={(event) => {
                  event.preventDefault();
                  onSelect(suggestion);
                  setIsOpen(false);
                }}
                className="flex w-full items-start justify-between gap-3 rounded-2xl px-4 py-3 text-left transition-colors hover:bg-slate-50"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-extrabold text-slate-800">
                    {suggestion.label}
                  </span>
                  {suggestion.secondary ? (
                    <span className="mt-1 block truncate text-xs font-medium text-slate-500">
                      {suggestion.secondary}
                    </span>
                  ) : null}
                </span>
                <span className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
                  {suggestion.type}
                </span>
              </button>
            ))
          ) : (
            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-500">
              {emptyText}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
