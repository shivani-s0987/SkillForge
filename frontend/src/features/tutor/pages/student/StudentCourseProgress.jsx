import React from 'react';

const StudentCourseProgress = ({ course }) => {
  return (
    <div className="p-4 mb-3 bg-white border rounded flex items-center justify-between">
      <div>
        <div className="font-semibold">{course.title}</div>
        <div className="text-sm text-gray-500">Watch Time: {course.watch_time} mins</div>
        <div className="text-sm text-gray-400">Started: {new Date(course.started_at).toLocaleDateString()}</div>
      </div>
      <div className="text-right">
        <div className="text-xl font-bold text-indigo-600">{course.progress}</div>
      </div>
    </div>
  )
}

export default StudentCourseProgress;
