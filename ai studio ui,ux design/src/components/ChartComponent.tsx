import React, { useMemo } from 'react';
import { motion } from 'motion/react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';

export interface ChartData {
  title: string;
  type: 'bar' | 'line';
  data: { name: string; value: number }[];
}

interface ChartComponentProps {
  jsonString: string;
}

export function ChartComponent({ jsonString }: ChartComponentProps) {
  const parsedData = useMemo<ChartData | null>(() => {
    try {
      if (!jsonString) return null;
      // In case Gemini returns markdown formatting like ```json ... ``` inside [CHART]
      const cleanJson = jsonString.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
      const parsed = JSON.parse(cleanJson);
      
      if (parsed && typeof parsed === 'object' && Array.isArray(parsed.data)) {
        return parsed as ChartData;
      }
      return null;
    } catch (e) {
      console.error('Failed to parse chart JSON:', e);
      return null;
    }
  }, [jsonString]);

  if (!parsedData || !parsedData.data.length || !['bar', 'line'].includes(parsedData.type)) {
    return null; // Don't render if data is invalid
  }

  const renderTooltip = (props: any) => {
    const { active, payload, label } = props;
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-xl shadow-slate-200/50">
          <p className="text-xs font-bold text-slate-500 mb-1">{label}</p>
          <p className="text-sm font-extrabold text-[#3B82F6]">
            {payload[0].value}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.6, type: 'spring', bounce: 0.3 }}
      className="my-5 p-5 bg-white border border-blue-100/50 rounded-2xl shadow-sm clay-card w-full"
    >
      <h4 className="text-left font-extrabold text-slate-800 mb-6 text-[15px] pl-2 border-l-4 border-[#3B82F6]">
        {parsedData.title || '데이터 분석 추이'}
      </h4>
      <div className="h-60 sm:h-72 w-full pr-4">
        <ResponsiveContainer width="100%" height="100%">
          {parsedData.type === 'line' ? (
            <LineChart data={parsedData.data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8', fontWeight: 700 }} tickLine={false} axisLine={false} tickMargin={10} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8', fontWeight: 700 }} tickLine={false} axisLine={false} tickMargin={10} />
              <Tooltip content={renderTooltip} cursor={{ fill: 'transparent', stroke: '#e2e8f0', strokeWidth: 1, strokeDasharray: '4 4' }} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#3B82F6"
                strokeWidth={3}
                dot={{ r: 4, fill: '#fff', strokeWidth: 2, stroke: '#3B82F6' }}
                activeDot={{ r: 7, fill: '#34D399', stroke: '#fff', strokeWidth: 2 }}
                animationDuration={1500}
                animationEasing="ease-in-out"
              />
            </LineChart>
          ) : (
            <BarChart data={parsedData.data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }} barSize={32}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8', fontWeight: 700 }} tickLine={false} axisLine={false} tickMargin={10} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8', fontWeight: 700 }} tickLine={false} axisLine={false} tickMargin={10} />
              <Tooltip cursor={{ fill: '#f8fafc' }} content={renderTooltip} />
              <Bar 
                dataKey="value" 
                fill="#3B82F6" 
                radius={[6, 6, 0, 0]} 
                animationDuration={1500} 
                animationEasing="ease-in-out" 
              />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
