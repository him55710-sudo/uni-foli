import React, { useState, useRef, useEffect } from 'react';
import { X, Star, Search, Plus } from 'lucide-react';
import type { CatalogSuggestion } from '../lib/educationCatalog';

interface CatalogMultiSelectInputProps {
  label: string;
  selectedUniversities: string[];
  representativeUniversity: string;
  suggestions: CatalogSuggestion[];
  onAdd: (name: string) => void;
  onRemove: (name: string) => void;
  onSetRepresentative: (name: string) => void;
  onInputChange: (value: string) => void;
  inputValue: string;
  placeholder: string;
  helperText?: string;
  emptyText?: string;
  disabled?: boolean;
}

export function CatalogMultiSelectInput({
  label,
  selectedUniversities,
  representativeUniversity,
  suggestions,
  onAdd,
  onRemove,
  onSetRepresentative,
  onInputChange,
  inputValue,
  placeholder,
  helperText,
  emptyText,
  disabled = false,
}: CatalogMultiSelectInputProps) {
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  
  const filteredSuggestions = suggestions.filter(
    (s) => !selectedUniversities.includes(s.label)
  );

  const shouldShowPanel = isOpen && (filteredSuggestions.length > 0 || (inputValue.trim().length > 0 && emptyText));

  return (
    <div className="relative">
      <label className="mb-3 block text-sm font-extrabold text-slate-700">{label}</label>
      
      {/* Selected Univ Chips */}
      <div className="mb-3 flex flex-wrap gap-2">
        {selectedUniversities.map((univ) => {
          const isRepresentative = univ === representativeUniversity;
          return (
            <div
              key={univ}
              className={`group flex items-center gap-2 rounded-2xl border-2 px-3 py-2 transition-all ${
                isRepresentative
                  ? 'border-blue-200 bg-blue-50 text-blue-700'
                  : 'border-slate-100 bg-slate-50 text-slate-600'
              }`}
            >
              <button
                type="button"
                onClick={() => onSetRepresentative(univ)}
                className={`flex h-6 w-6 items-center justify-center rounded-lg transition-colors ${
                  isRepresentative ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-400 hover:bg-slate-300'
                }`}
                title={isRepresentative ? '대표 대학' : '대표 대학으로 설정'}
              >
                <Star size={14} fill={isRepresentative ? 'currentColor' : 'none'} />
              </button>
              
              <span className="text-sm font-bold">{univ}</span>
              
              <button
                type="button"
                disabled={disabled}
                onClick={() => onRemove(univ)}
                className="flex h-5 w-5 items-center justify-center rounded-full text-slate-400 hover:bg-slate-200 hover:text-slate-600"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="relative">
        <div className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-400">
          <Search size={20} />
        </div>
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          disabled={disabled}
          placeholder={selectedUniversities.length > 0 ? '추가 대학 검색...' : placeholder}
          onFocus={() => setIsOpen(true)}
          onBlur={() => {
            window.setTimeout(() => setIsOpen(false), 200);
          }}
          onChange={(event) => {
            onInputChange(event.target.value);
            setIsOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Backspace' && inputValue === '' && selectedUniversities.length > 0) {
              onRemove(selectedUniversities[selectedUniversities.length - 1]);
            }
          }}
          className="w-full rounded-3xl border-2 border-slate-100 bg-slate-50 py-4 pl-14 pr-5 text-lg font-bold text-slate-800 shadow-sm outline-none transition-all placeholder:text-slate-300 focus:border-blue-400 focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
        />
      </div>

      {helperText ? (
        <p className="mt-2 text-xs font-medium leading-relaxed text-slate-500">{helperText}</p>
      ) : null}

      {shouldShowPanel ? (
        <div className="absolute left-0 right-0 z-30 mt-3 max-h-72 overflow-y-auto rounded-3xl border border-slate-200 bg-white p-2 shadow-2xl">
          {filteredSuggestions.length ? (
            filteredSuggestions.map((suggestion) => (
              <button
                key={suggestion.id}
                type="button"
                onMouseDown={(event) => {
                  event.preventDefault();
                  onAdd(suggestion.label);
                  onInputChange('');
                  setIsOpen(false);
                }}
                className="flex w-full items-start justify-between gap-3 rounded-2xl px-4 py-3 text-left transition-colors hover:bg-slate-50"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-extrabold text-slate-800">
                    {suggestion.label}
                  </span>
                </span>
                <Plus size={16} className="text-slate-300" />
              </button>
            ))
          ) : (
            <div 
              onMouseDown={(e) => {
                if (inputValue.trim()) {
                  e.preventDefault();
                  onAdd(inputValue.trim());
                  onInputChange('');
                  setIsOpen(false);
                }
              }}
              className="group cursor-pointer rounded-2xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-500 hover:bg-blue-50 hover:text-blue-600"
            >
              {emptyText} <span className="font-bold">"{inputValue}"</span> 추가하기
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
