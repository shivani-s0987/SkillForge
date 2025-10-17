import React from 'react';
import { useNavigate } from 'react-router-dom';

const StudentCard = ({ student }) => {
  const navigate = useNavigate();
  return (
    <div onClick={() => navigate(`/tutor/student/${student.id}`)} className="cursor-pointer flex items-center space-x-4 p-3 border-b last:border-b-0 hover:bg-indigo-50">
      <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold">{(student.name||'U').charAt(0).toUpperCase()}</div>
      <div className="flex-1">
        <div className="font-semibold">{student.name}</div>
        <div className="text-sm text-gray-500">{student.email}</div>
        <div className="text-xs text-gray-400 mt-1">Courses: {student.enrolled_courses_count} • Tests: {student.total_tests}</div>
      </div>
      <div className="text-right">
        <div className="text-sm font-semibold text-indigo-600">{student.completion_pct ?? 0}%</div>
        <div className="text-xs text-gray-400">Completion</div>
      </div>
    </div>
  )
}

export default StudentCard;
