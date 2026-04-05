import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { BookOpen, Newspaper, GraduationCap, Lightbulb, ChevronDown, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';

type TrendType = '도서 추천' | '입시 이슈' | '합격 가이드' | '탐구 아이디어';

interface TrendItem {
  id: number;
  type: TrendType;
  icon: React.ComponentType<{ size?: number }>;
  title: string;
  desc: string;
}

const trendItems: TrendItem[] = [
  { id: 121, type: "도서 추천", icon: BookOpen, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 122, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 123, type: "합격 가이드", icon: GraduationCap, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 124, type: "도서 추천", icon: BookOpen, title: "[통계] 심화 탐구 로드맵", desc: "통계 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 125, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 실전 탐구 로드맵", desc: "미디어 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 126, type: "도서 추천", icon: BookOpen, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 127, type: "탐구 아이디어", icon: Lightbulb, title: "[치의예과] 실전 탐구 로드맵", desc: "치의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 128, type: "입시 이슈", icon: Newspaper, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 129, type: "합격 가이드", icon: GraduationCap, title: "[전자] 혁신 탐구 로드맵", desc: "전자 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 130, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 실전 탐구 로드맵", desc: "미디어 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 131, type: "도서 추천", icon: BookOpen, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 132, type: "입시 이슈", icon: Newspaper, title: "[교육] 글로벌 탐구 로드맵", desc: "교육 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 133, type: "입시 이슈", icon: Newspaper, title: "[미디어] 심화 탐구 로드맵", desc: "미디어 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 134, type: "도서 추천", icon: BookOpen, title: "[경영] 실전 탐구 로드맵", desc: "경영 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 135, type: "입시 이슈", icon: Newspaper, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 136, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 137, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 138, type: "탐구 아이디어", icon: Lightbulb, title: "[약학과] 혁신 탐구 로드맵", desc: "약학과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 139, type: "입시 이슈", icon: Newspaper, title: "[컴공] 글로벌 탐구 로드맵", desc: "컴공 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 140, type: "합격 가이드", icon: GraduationCap, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 141, type: "합격 가이드", icon: GraduationCap, title: "[법학] 글로벌 탐구 로드맵", desc: "법학 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 142, type: "도서 추천", icon: BookOpen, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 143, type: "합격 가이드", icon: GraduationCap, title: "[통계] 실전 탐구 로드맵", desc: "통계 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 144, type: "탐구 아이디어", icon: Lightbulb, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 145, type: "입시 이슈", icon: Newspaper, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 146, type: "입시 이슈", icon: Newspaper, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 147, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 148, type: "도서 추천", icon: BookOpen, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 149, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 150, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 심화 탐구 로드맵", desc: "경영 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 151, type: "도서 추천", icon: BookOpen, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 152, type: "탐구 아이디어", icon: Lightbulb, title: "[컴공] 글로벌 탐구 로드맵", desc: "컴공 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 153, type: "탐구 아이디어", icon: Lightbulb, title: "[미디어] 실전 탐구 로드맵", desc: "미디어 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 154, type: "입시 이슈", icon: Newspaper, title: "[심리] 혁신 탐구 로드맵", desc: "심리 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 155, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 심화 탐구 로드맵", desc: "미디어 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 156, type: "합격 가이드", icon: GraduationCap, title: "[법학] 혁신 탐구 로드맵", desc: "법학 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 157, type: "도서 추천", icon: BookOpen, title: "[법학] 혁신 탐구 로드맵", desc: "법학 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 158, type: "도서 추천", icon: BookOpen, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 159, type: "도서 추천", icon: BookOpen, title: "[통계] 실전 탐구 로드맵", desc: "통계 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 160, type: "입시 이슈", icon: Newspaper, title: "[의예과] 글로벌 탐구 로드맵", desc: "의예과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 161, type: "도서 추천", icon: BookOpen, title: "[통계] 심화 탐구 로드맵", desc: "통계 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 162, type: "도서 추천", icon: BookOpen, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 163, type: "합격 가이드", icon: GraduationCap, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 164, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 165, type: "입시 이슈", icon: Newspaper, title: "[미디어] 실전 탐구 로드맵", desc: "미디어 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 166, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 혁신 탐구 로드맵", desc: "경영 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 167, type: "입시 이슈", icon: Newspaper, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 168, type: "도서 추천", icon: BookOpen, title: "[약학과] 글로벌 탐구 로드맵", desc: "약학과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 169, type: "도서 추천", icon: BookOpen, title: "[도시] 글로벌 탐구 로드맵", desc: "도시 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 170, type: "합격 가이드", icon: GraduationCap, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 171, type: "도서 추천", icon: BookOpen, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 172, type: "도서 추천", icon: BookOpen, title: "[정외] 심화 탐구 로드맵", desc: "정외 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 173, type: "탐구 아이디어", icon: Lightbulb, title: "[치의예과] 실전 탐구 로드맵", desc: "치의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 174, type: "입시 이슈", icon: Newspaper, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 175, type: "도서 추천", icon: BookOpen, title: "[컴공] 심화 탐구 로드맵", desc: "컴공 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 176, type: "합격 가이드", icon: GraduationCap, title: "[약학과] 실전 탐구 로드맵", desc: "약학과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 177, type: "합격 가이드", icon: GraduationCap, title: "[정외] 심화 탐구 로드맵", desc: "정외 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 178, type: "입시 이슈", icon: Newspaper, title: "[치의예과] 혁신 탐구 로드맵", desc: "치의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 179, type: "도서 추천", icon: BookOpen, title: "[컴공] 심화 탐구 로드맵", desc: "컴공 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 180, type: "도서 추천", icon: BookOpen, title: "[전자] 실전 탐구 로드맵", desc: "전자 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 181, type: "도서 추천", icon: BookOpen, title: "[의예과] 글로벌 탐구 로드맵", desc: "의예과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 182, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 글로벌 탐구 로드맵", desc: "생명 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 183, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 심화 탐구 로드맵", desc: "미디어 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 184, type: "합격 가이드", icon: GraduationCap, title: "[교육] 심화 탐구 로드맵", desc: "교육 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 185, type: "도서 추천", icon: BookOpen, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 186, type: "합격 가이드", icon: GraduationCap, title: "[도시] 혁신 탐구 로드맵", desc: "도시 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 187, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 188, type: "도서 추천", icon: BookOpen, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 189, type: "합격 가이드", icon: GraduationCap, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 190, type: "합격 가이드", icon: GraduationCap, title: "[전자] 혁신 탐구 로드맵", desc: "전자 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 191, type: "도서 추천", icon: BookOpen, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 192, type: "도서 추천", icon: BookOpen, title: "[도시] 혁신 탐구 로드맵", desc: "도시 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 193, type: "탐구 아이디어", icon: Lightbulb, title: "[치의예과] 심화 탐구 로드맵", desc: "치의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 194, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 혁신 탐구 로드맵", desc: "경영 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 195, type: "도서 추천", icon: BookOpen, title: "[경영] 글로벌 탐구 로드맵", desc: "경영 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 196, type: "입시 이슈", icon: Newspaper, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 197, type: "입시 이슈", icon: Newspaper, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 198, type: "도서 추천", icon: BookOpen, title: "[정외] 실전 탐구 로드맵", desc: "정외 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 199, type: "탐구 아이디어", icon: Lightbulb, title: "[약학과] 실전 탐구 로드맵", desc: "약학과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 200, type: "입시 이슈", icon: Newspaper, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 201, type: "입시 이슈", icon: Newspaper, title: "[교육] 글로벌 탐구 로드맵", desc: "교육 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 202, type: "입시 이슈", icon: Newspaper, title: "[컴공] 실전 탐구 로드맵", desc: "컴공 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 203, type: "입시 이슈", icon: Newspaper, title: "[치의예과] 실전 탐구 로드맵", desc: "치의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 204, type: "입시 이슈", icon: Newspaper, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 205, type: "합격 가이드", icon: GraduationCap, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 206, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 실전 탐구 로드맵", desc: "미디어 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 207, type: "탐구 아이디어", icon: Lightbulb, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 208, type: "입시 이슈", icon: Newspaper, title: "[심리] 혁신 탐구 로드맵", desc: "심리 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 209, type: "합격 가이드", icon: GraduationCap, title: "[컴공] 혁신 탐구 로드맵", desc: "컴공 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 210, type: "도서 추천", icon: BookOpen, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 211, type: "탐구 아이디어", icon: Lightbulb, title: "[법학] 심화 탐구 로드맵", desc: "법학 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 212, type: "탐구 아이디어", icon: Lightbulb, title: "[통계] 심화 탐구 로드맵", desc: "통계 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 213, type: "합격 가이드", icon: GraduationCap, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 214, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 215, type: "도서 추천", icon: BookOpen, title: "[법학] 글로벌 탐구 로드맵", desc: "법학 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 216, type: "입시 이슈", icon: Newspaper, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 217, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 심화 탐구 로드맵", desc: "생명 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 218, type: "입시 이슈", icon: Newspaper, title: "[의예과] 혁신 탐구 로드맵", desc: "의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 219, type: "탐구 아이디어", icon: Lightbulb, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 220, type: "입시 이슈", icon: Newspaper, title: "[법학] 심화 탐구 로드맵", desc: "법학 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 221, type: "도서 추천", icon: BookOpen, title: "[생명] 글로벌 탐구 로드맵", desc: "생명 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 222, type: "입시 이슈", icon: Newspaper, title: "[정외] 실전 탐구 로드맵", desc: "정외 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 223, type: "입시 이슈", icon: Newspaper, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 224, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 글로벌 탐구 로드맵", desc: "교육 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 225, type: "합격 가이드", icon: GraduationCap, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 226, type: "도서 추천", icon: BookOpen, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 227, type: "탐구 아이디어", icon: Lightbulb, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 228, type: "탐구 아이디어", icon: Lightbulb, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 229, type: "입시 이슈", icon: Newspaper, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 230, type: "합격 가이드", icon: GraduationCap, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 231, type: "도서 추천", icon: BookOpen, title: "[생명] 글로벌 탐구 로드맵", desc: "생명 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 232, type: "합격 가이드", icon: GraduationCap, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 233, type: "합격 가이드", icon: GraduationCap, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 234, type: "합격 가이드", icon: GraduationCap, title: "[법학] 글로벌 탐구 로드맵", desc: "법학 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 235, type: "입시 이슈", icon: Newspaper, title: "[전자] 글로벌 탐구 로드맵", desc: "전자 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 236, type: "입시 이슈", icon: Newspaper, title: "[법학] 글로벌 탐구 로드맵", desc: "법학 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 237, type: "탐구 아이디어", icon: Lightbulb, title: "[치의예과] 혁신 탐구 로드맵", desc: "치의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 238, type: "입시 이슈", icon: Newspaper, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 239, type: "탐구 아이디어", icon: Lightbulb, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 240, type: "도서 추천", icon: BookOpen, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 241, type: "도서 추천", icon: BookOpen, title: "[약학과] 실전 탐구 로드맵", desc: "약학과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 242, type: "탐구 아이디어", icon: Lightbulb, title: "[약학과] 실전 탐구 로드맵", desc: "약학과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 243, type: "도서 추천", icon: BookOpen, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 244, type: "도서 추천", icon: BookOpen, title: "[교육] 심화 탐구 로드맵", desc: "교육 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 245, type: "입시 이슈", icon: Newspaper, title: "[통계] 혁신 탐구 로드맵", desc: "통계 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 246, type: "도서 추천", icon: BookOpen, title: "[미디어] 실전 탐구 로드맵", desc: "미디어 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 247, type: "탐구 아이디어", icon: Lightbulb, title: "[통계] 혁신 탐구 로드맵", desc: "통계 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 248, type: "도서 추천", icon: BookOpen, title: "[치의예과] 실전 탐구 로드맵", desc: "치의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 249, type: "합격 가이드", icon: GraduationCap, title: "[경영] 글로벌 탐구 로드맵", desc: "경영 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 250, type: "도서 추천", icon: BookOpen, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 251, type: "도서 추천", icon: BookOpen, title: "[경영] 혁신 탐구 로드맵", desc: "경영 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 252, type: "입시 이슈", icon: Newspaper, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 253, type: "합격 가이드", icon: GraduationCap, title: "[도시] 혁신 탐구 로드맵", desc: "도시 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 254, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 심화 탐구 로드맵", desc: "생명 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 255, type: "도서 추천", icon: BookOpen, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 256, type: "도서 추천", icon: BookOpen, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 257, type: "도서 추천", icon: BookOpen, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 258, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 실전 탐구 로드맵", desc: "생명 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 259, type: "탐구 아이디어", icon: Lightbulb, title: "[도시] 혁신 탐구 로드맵", desc: "도시 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 260, type: "도서 추천", icon: BookOpen, title: "[컴공] 혁신 탐구 로드맵", desc: "컴공 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 261, type: "합격 가이드", icon: GraduationCap, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 262, type: "탐구 아이디어", icon: Lightbulb, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 263, type: "입시 이슈", icon: Newspaper, title: "[치의예과] 글로벌 탐구 로드맵", desc: "치의예과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 264, type: "도서 추천", icon: BookOpen, title: "[미디어] 심화 탐구 로드맵", desc: "미디어 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 265, type: "도서 추천", icon: BookOpen, title: "[컴공] 글로벌 탐구 로드맵", desc: "컴공 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 266, type: "합격 가이드", icon: GraduationCap, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 267, type: "입시 이슈", icon: Newspaper, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 268, type: "도서 추천", icon: BookOpen, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 269, type: "합격 가이드", icon: GraduationCap, title: "[치의예과] 혁신 탐구 로드맵", desc: "치의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 270, type: "도서 추천", icon: BookOpen, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 271, type: "합격 가이드", icon: GraduationCap, title: "[전자] 실전 탐구 로드맵", desc: "전자 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 272, type: "입시 이슈", icon: Newspaper, title: "[심리] 혁신 탐구 로드맵", desc: "심리 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 273, type: "탐구 아이디어", icon: Lightbulb, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 274, type: "도서 추천", icon: BookOpen, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 275, type: "입시 이슈", icon: Newspaper, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 276, type: "도서 추천", icon: BookOpen, title: "[경영] 실전 탐구 로드맵", desc: "경영 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 277, type: "도서 추천", icon: BookOpen, title: "[도시] 글로벌 탐구 로드맵", desc: "도시 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 278, type: "입시 이슈", icon: Newspaper, title: "[경영] 실전 탐구 로드맵", desc: "경영 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 279, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 280, type: "합격 가이드", icon: GraduationCap, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 281, type: "도서 추천", icon: BookOpen, title: "[심리] 혁신 탐구 로드맵", desc: "심리 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 282, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 283, type: "입시 이슈", icon: Newspaper, title: "[미디어] 심화 탐구 로드맵", desc: "미디어 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 284, type: "입시 이슈", icon: Newspaper, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 285, type: "도서 추천", icon: BookOpen, title: "[전자] 글로벌 탐구 로드맵", desc: "전자 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 286, type: "탐구 아이디어", icon: Lightbulb, title: "[컴공] 혁신 탐구 로드맵", desc: "컴공 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 287, type: "입시 이슈", icon: Newspaper, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 288, type: "도서 추천", icon: BookOpen, title: "[경영] 글로벌 탐구 로드맵", desc: "경영 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 289, type: "도서 추천", icon: BookOpen, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 290, type: "입시 이슈", icon: Newspaper, title: "[의예과] 혁신 탐구 로드맵", desc: "의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 291, type: "도서 추천", icon: BookOpen, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 292, type: "도서 추천", icon: BookOpen, title: "[컴공] 심화 탐구 로드맵", desc: "컴공 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 293, type: "입시 이슈", icon: Newspaper, title: "[약학과] 혁신 탐구 로드맵", desc: "약학과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 294, type: "입시 이슈", icon: Newspaper, title: "[통계] 실전 탐구 로드맵", desc: "통계 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 295, type: "도서 추천", icon: BookOpen, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 296, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 실전 탐구 로드맵", desc: "생명 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 297, type: "합격 가이드", icon: GraduationCap, title: "[생명] 글로벌 탐구 로드맵", desc: "생명 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 298, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 299, type: "탐구 아이디어", icon: Lightbulb, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 300, type: "도서 추천", icon: BookOpen, title: "[도시] 글로벌 탐구 로드맵", desc: "도시 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 301, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 혁신 탐구 로드맵", desc: "경영 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 302, type: "입시 이슈", icon: Newspaper, title: "[전자] 글로벌 탐구 로드맵", desc: "전자 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 303, type: "합격 가이드", icon: GraduationCap, title: "[정외] 심화 탐구 로드맵", desc: "정외 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 304, type: "도서 추천", icon: BookOpen, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 305, type: "합격 가이드", icon: GraduationCap, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 306, type: "도서 추천", icon: BookOpen, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 307, type: "탐구 아이디어", icon: Lightbulb, title: "[컴공] 실전 탐구 로드맵", desc: "컴공 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 308, type: "도서 추천", icon: BookOpen, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 309, type: "탐구 아이디어", icon: Lightbulb, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 310, type: "입시 이슈", icon: Newspaper, title: "[도시] 글로벌 탐구 로드맵", desc: "도시 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 311, type: "입시 이슈", icon: Newspaper, title: "[컴공] 혁신 탐구 로드맵", desc: "컴공 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 312, type: "탐구 아이디어", icon: Lightbulb, title: "[컴공] 실전 탐구 로드맵", desc: "컴공 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 313, type: "합격 가이드", icon: GraduationCap, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 314, type: "도서 추천", icon: BookOpen, title: "[법학] 글로벌 탐구 로드맵", desc: "법학 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 315, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 심화 탐구 로드맵", desc: "정외 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 316, type: "탐구 아이디어", icon: Lightbulb, title: "[통계] 심화 탐구 로드맵", desc: "통계 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 317, type: "합격 가이드", icon: GraduationCap, title: "[정외] 심화 탐구 로드맵", desc: "정외 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 318, type: "도서 추천", icon: BookOpen, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 319, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 혁신 탐구 로드맵", desc: "생명 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 320, type: "탐구 아이디어", icon: Lightbulb, title: "[미디어] 글로벌 탐구 로드맵", desc: "미디어 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 321, type: "도서 추천", icon: BookOpen, title: "[심리] 혁신 탐구 로드맵", desc: "심리 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 322, type: "합격 가이드", icon: GraduationCap, title: "[생명] 글로벌 탐구 로드맵", desc: "생명 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 323, type: "탐구 아이디어", icon: Lightbulb, title: "[미디어] 글로벌 탐구 로드맵", desc: "미디어 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 324, type: "입시 이슈", icon: Newspaper, title: "[약학과] 혁신 탐구 로드맵", desc: "약학과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 325, type: "입시 이슈", icon: Newspaper, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 326, type: "입시 이슈", icon: Newspaper, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 327, type: "입시 이슈", icon: Newspaper, title: "[생명] 실전 탐구 로드맵", desc: "생명 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 328, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 실전 탐구 로드맵", desc: "경영 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 329, type: "입시 이슈", icon: Newspaper, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 330, type: "도서 추천", icon: BookOpen, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 331, type: "합격 가이드", icon: GraduationCap, title: "[치의예과] 실전 탐구 로드맵", desc: "치의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 332, type: "도서 추천", icon: BookOpen, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 333, type: "입시 이슈", icon: Newspaper, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 334, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 글로벌 탐구 로드맵", desc: "경영 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 335, type: "입시 이슈", icon: Newspaper, title: "[경영] 심화 탐구 로드맵", desc: "경영 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 336, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 심화 탐구 로드맵", desc: "경영 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 337, type: "합격 가이드", icon: GraduationCap, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 338, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 심화 탐구 로드맵", desc: "경영 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 339, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 340, type: "도서 추천", icon: BookOpen, title: "[미디어] 심화 탐구 로드맵", desc: "미디어 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 341, type: "합격 가이드", icon: GraduationCap, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 342, type: "입시 이슈", icon: Newspaper, title: "[교육] 혁신 탐구 로드맵", desc: "교육 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 343, type: "입시 이슈", icon: Newspaper, title: "[경영] 혁신 탐구 로드맵", desc: "경영 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 344, type: "입시 이슈", icon: Newspaper, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 345, type: "도서 추천", icon: BookOpen, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 346, type: "도서 추천", icon: BookOpen, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 347, type: "입시 이슈", icon: Newspaper, title: "[약학과] 혁신 탐구 로드맵", desc: "약학과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 348, type: "도서 추천", icon: BookOpen, title: "[통계] 심화 탐구 로드맵", desc: "통계 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 349, type: "입시 이슈", icon: Newspaper, title: "[경영] 글로벌 탐구 로드맵", desc: "경영 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 350, type: "입시 이슈", icon: Newspaper, title: "[약학과] 심화 탐구 로드맵", desc: "약학과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 351, type: "탐구 아이디어", icon: Lightbulb, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 352, type: "도서 추천", icon: BookOpen, title: "[생명] 실전 탐구 로드맵", desc: "생명 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 353, type: "탐구 아이디어", icon: Lightbulb, title: "[통계] 글로벌 탐구 로드맵", desc: "통계 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 354, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 글로벌 탐구 로드맵", desc: "의예과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 355, type: "도서 추천", icon: BookOpen, title: "[약학과] 글로벌 탐구 로드맵", desc: "약학과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 356, type: "도서 추천", icon: BookOpen, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 357, type: "입시 이슈", icon: Newspaper, title: "[의예과] 혁신 탐구 로드맵", desc: "의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 358, type: "탐구 아이디어", icon: Lightbulb, title: "[치의예과] 혁신 탐구 로드맵", desc: "치의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 359, type: "도서 추천", icon: BookOpen, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 360, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 실전 탐구 로드맵", desc: "경영 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 361, type: "합격 가이드", icon: GraduationCap, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 362, type: "입시 이슈", icon: Newspaper, title: "[생명] 글로벌 탐구 로드맵", desc: "생명 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 363, type: "도서 추천", icon: BookOpen, title: "[컴공] 글로벌 탐구 로드맵", desc: "컴공 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 364, type: "도서 추천", icon: BookOpen, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 365, type: "합격 가이드", icon: GraduationCap, title: "[생명] 실전 탐구 로드맵", desc: "생명 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 366, type: "도서 추천", icon: BookOpen, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 367, type: "탐구 아이디어", icon: Lightbulb, title: "[생명] 실전 탐구 로드맵", desc: "생명 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 368, type: "도서 추천", icon: BookOpen, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 369, type: "입시 이슈", icon: Newspaper, title: "[심리] 심화 탐구 로드맵", desc: "심리 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 370, type: "도서 추천", icon: BookOpen, title: "[컴공] 실전 탐구 로드맵", desc: "컴공 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 371, type: "입시 이슈", icon: Newspaper, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 372, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 373, type: "도서 추천", icon: BookOpen, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 374, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 375, type: "입시 이슈", icon: Newspaper, title: "[통계] 혁신 탐구 로드맵", desc: "통계 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 376, type: "탐구 아이디어", icon: Lightbulb, title: "[통계] 심화 탐구 로드맵", desc: "통계 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 377, type: "합격 가이드", icon: GraduationCap, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 378, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 심화 탐구 로드맵", desc: "교육 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 379, type: "합격 가이드", icon: GraduationCap, title: "[전자] 글로벌 탐구 로드맵", desc: "전자 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 380, type: "합격 가이드", icon: GraduationCap, title: "[약학과] 실전 탐구 로드맵", desc: "약학과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 381, type: "입시 이슈", icon: Newspaper, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 382, type: "합격 가이드", icon: GraduationCap, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 383, type: "합격 가이드", icon: GraduationCap, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 384, type: "합격 가이드", icon: GraduationCap, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 385, type: "합격 가이드", icon: GraduationCap, title: "[교육] 실전 탐구 로드맵", desc: "교육 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 386, type: "탐구 아이디어", icon: Lightbulb, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 387, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 심화 탐구 로드맵", desc: "교육 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 388, type: "합격 가이드", icon: GraduationCap, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 389, type: "탐구 아이디어", icon: Lightbulb, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 390, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 글로벌 탐구 로드맵", desc: "정외 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 391, type: "입시 이슈", icon: Newspaper, title: "[도시] 글로벌 탐구 로드맵", desc: "도시 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 392, type: "입시 이슈", icon: Newspaper, title: "[생명] 심화 탐구 로드맵", desc: "생명 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 393, type: "도서 추천", icon: BookOpen, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 394, type: "탐구 아이디어", icon: Lightbulb, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 395, type: "탐구 아이디어", icon: Lightbulb, title: "[교육] 심화 탐구 로드맵", desc: "교육 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 396, type: "합격 가이드", icon: GraduationCap, title: "[전자] 심화 탐구 로드맵", desc: "전자 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 397, type: "도서 추천", icon: BookOpen, title: "[컴공] 실전 탐구 로드맵", desc: "컴공 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 398, type: "입시 이슈", icon: Newspaper, title: "[심리] 글로벌 탐구 로드맵", desc: "심리 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 399, type: "탐구 아이디어", icon: Lightbulb, title: "[치의예과] 심화 탐구 로드맵", desc: "치의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 400, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 글로벌 탐구 로드맵", desc: "의예과 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 401, type: "도서 추천", icon: BookOpen, title: "[의예과] 실전 탐구 로드맵", desc: "의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 402, type: "탐구 아이디어", icon: Lightbulb, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 403, type: "도서 추천", icon: BookOpen, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 404, type: "합격 가이드", icon: GraduationCap, title: "[치의예과] 심화 탐구 로드맵", desc: "치의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 405, type: "탐구 아이디어", icon: Lightbulb, title: "[미디어] 혁신 탐구 로드맵", desc: "미디어 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 406, type: "도서 추천", icon: BookOpen, title: "[경영] 혁신 탐구 로드맵", desc: "경영 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 407, type: "입시 이슈", icon: Newspaper, title: "[법학] 혁신 탐구 로드맵", desc: "법학 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 408, type: "도서 추천", icon: BookOpen, title: "[법학] 글로벌 탐구 로드맵", desc: "법학 지망생을 위한 글로벌 핵심 전략 자료입니다." },
  { id: 409, type: "도서 추천", icon: BookOpen, title: "[치의예과] 실전 탐구 로드맵", desc: "치의예과 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 410, type: "도서 추천", icon: BookOpen, title: "[치의예과] 혁신 탐구 로드맵", desc: "치의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 411, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 심화 탐구 로드맵", desc: "의예과 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 412, type: "입시 이슈", icon: Newspaper, title: "[전자] 실전 탐구 로드맵", desc: "전자 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 413, type: "탐구 아이디어", icon: Lightbulb, title: "[심리] 실전 탐구 로드맵", desc: "심리 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 414, type: "탐구 아이디어", icon: Lightbulb, title: "[경영] 실전 탐구 로드맵", desc: "경영 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 415, type: "입시 이슈", icon: Newspaper, title: "[도시] 혁신 탐구 로드맵", desc: "도시 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 416, type: "입시 이슈", icon: Newspaper, title: "[도시] 심화 탐구 로드맵", desc: "도시 지망생을 위한 심화 핵심 전략 자료입니다." },
  { id: 417, type: "탐구 아이디어", icon: Lightbulb, title: "[법학] 실전 탐구 로드맵", desc: "법학 지망생을 위한 실전 핵심 전략 자료입니다." },
  { id: 418, type: "탐구 아이디어", icon: Lightbulb, title: "[정외] 혁신 탐구 로드맵", desc: "정외 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 419, type: "탐구 아이디어", icon: Lightbulb, title: "[의예과] 혁신 탐구 로드맵", desc: "의예과 지망생을 위한 혁신 핵심 전략 자료입니다." },
  { id: 420, type: "입시 이슈", icon: Newspaper, title: "[도시] 실전 탐구 로드맵", desc: "도시 지망생을 위한 실전 핵심 전략 자료입니다." },];

const baseFilters = ['전체', '도서 추천', '입시 이슈', '합격 가이드', '탐구 아이디어'] as const;

export function Trends() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<string>('전체');
  const [extraFilters, setExtraFilters] = useState<string[]>([]);
  const [selectedTrend, setSelectedTrend] = useState<TrendItem | null>(null);

  const allFilters = useMemo(() => [...baseFilters, ...extraFilters], [extraFilters]);

  const visibleItems = useMemo(() => {
    if (activeFilter === '전체') return trendItems;
    return trendItems.filter((item) => item.type === activeFilter);
  }, [activeFilter]);

  const handleAddFilter = () => {
    const input = window.prompt('관심 전공 키워드를 입력해주세요. (예: 컴퓨터공학)');
    const value = input?.trim();
    if (!value) return;
    if (extraFilters.includes(value)) {
      toast('이미 추가된 필터입니다.', { icon: 'ℹ️' });
      return;
    }
    setExtraFilters((prev) => [...prev, value]);
    setActiveFilter('전체');
    toast.success(`"${value}" 필터를 추가했습니다.`);
  };

  return (
    <div className="mx-auto max-w-7xl px-0 pb-24 sm:px-2 lg:px-4">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <h1 className="mb-2 text-3xl font-extrabold tracking-tight text-slate-800 sm:text-4xl">입시 트렌드 허브</h1>
        <p className="text-base font-medium text-slate-500 sm:text-lg">
          전공과 목표에 맞는 자료를 골라 보고서 주제로 바로 연결하세요.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-10 flex flex-wrap gap-3"
      >
        {allFilters.map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`rounded-full px-5 py-2.5 text-sm font-extrabold shadow-sm transition-all ${
              activeFilter === filter
                ? 'scale-105 bg-slate-800 text-white shadow-md'
                : 'border border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600'
            }`}
          >
            {filter}
          </button>
        ))}
        <button
          onClick={handleAddFilter}
          className="flex items-center gap-2 rounded-full border border-dashed border-slate-300 bg-slate-50 px-5 py-2.5 text-sm font-extrabold text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        >
          관심 전공 추가 <ChevronDown size={16} />
        </button>
      </motion.div>

      <div className="grid grid-cols-1 items-start gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {visibleItems.map((item, index) => (
          <motion.button
            type="button"
            key={item.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => setSelectedTrend(item)}
            className="group flex h-auto min-h-[290px] w-full self-start cursor-pointer flex-col overflow-hidden p-5 text-left sm:h-[320px] sm:p-8 clay-card"
          >
            <div
              className={`mb-4 inline-flex w-fit items-center gap-2 rounded-xl border px-3 py-1.5 text-xs font-extrabold ${
                item.type === '도서 추천'
                  ? 'border-blue-100 bg-blue-50 text-blue-600'
                  : item.type === '입시 이슈'
                    ? 'border-emerald-100 bg-emerald-50 text-emerald-600'
                    : item.type === '합격 가이드'
                      ? 'border-indigo-100 bg-indigo-50 text-indigo-600'
                      : 'border-amber-100 bg-amber-50 text-amber-600'
              }`}
            >
              <item.icon size={16} />
              {item.type}
            </div>
            <h3 className="mb-2 h-[2.75rem] line-clamp-2 text-lg font-extrabold leading-tight text-slate-800 transition-colors group-hover:text-blue-600">
              {item.title}
            </h3>
            <p className="mb-4 h-[4.5rem] line-clamp-3 text-sm font-medium leading-relaxed text-slate-500">
              {item.desc}
            </p>

            <div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-4">
              <span className="rounded-lg bg-slate-50 px-2.5 py-1 text-xs font-bold text-slate-400">조회수 1.2k</span>
              <span className="flex items-center gap-1.5 rounded-xl border border-slate-100 bg-white px-3 py-1.5 text-sm font-extrabold text-slate-800 shadow-sm transition-colors group-hover:border-blue-200 group-hover:text-blue-600">
                자세히 <span className="transition-transform group-hover:translate-x-1">→</span>
              </span>
            </div>
          </motion.button>
        ))}
      </div>

      <AnimatePresence>
        {selectedTrend ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedTrend(null)}
            className="fixed inset-0 z-50 flex items-end bg-slate-900/40 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
          >
            <motion.div
              initial={{ opacity: 0, y: 60 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 60 }}
              onClick={(event) => event.stopPropagation()}
              className="relative w-full max-h-[88dvh] overflow-y-auto rounded-t-3xl bg-white p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-2xl sm:max-h-[80dvh] sm:max-w-2xl sm:rounded-3xl sm:p-8"
            >
              <button
                onClick={() => setSelectedTrend(null)}
                className="absolute right-4 top-4 rounded-full bg-slate-100 p-2 text-slate-500 transition-colors hover:text-slate-700"
              >
                <X size={18} />
              </button>
              <div className="mb-5 inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-extrabold text-blue-600">
                <selectedTrend.icon size={16} />
                {selectedTrend.type}
              </div>
              <h3 className="mb-3 text-2xl font-extrabold leading-snug text-slate-800">{selectedTrend.title}</h3>
              <p className="mb-6 text-[15px] font-medium leading-relaxed text-slate-600">{selectedTrend.desc}</p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(selectedTrend.title);
                    toast.success('주제 제목을 클립보드에 복사했습니다.');
                  }}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-bold text-slate-700 transition-colors hover:bg-slate-50"
                >
                  제목 복사
                </button>
                <button
                  onClick={() => {
                    navigate(`/app/workshop?major=${encodeURIComponent(selectedTrend.type)}`);
                    toast.success('선택한 주제로 워크숍을 열었습니다.');
                    setSelectedTrend(null);
                  }}
                  className="rounded-xl bg-blue-500 px-4 py-2.5 font-bold text-white transition-colors hover:bg-blue-600"
                >
                  이 주제로 작성 시작
                </button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
