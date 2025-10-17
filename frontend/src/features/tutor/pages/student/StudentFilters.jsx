import React, { useState } from 'react';
import { motion } from 'framer-motion';

const StudentFilters = () => {
  const [query, setQuery] = useState('');
  const [course, setCourse] = useState('all');

  return (
    <motion.div initial={{opacity:0}} animate={{opacity:1}} className="mt-4 bg-white p-4 rounded-lg shadow flex flex-col lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center space-x-3">
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search students, emails..." className="px-3 py-2 border rounded w-64" />
        <select value={course} onChange={e=>setCourse(e.target.value)} className="px-3 py-2 border rounded">
          <option value="all">All Courses</option>
          <option value="course1">Course 1</option>
        </select>
        <button className="bg-indigo-600 text-white px-4 py-2 rounded">Apply</button>
      </div>
      <div className="mt-3 lg:mt-0 text-sm text-gray-500">Filter by course, performance or tests. Live updates every 30s.</div>
    </motion.div>
  )
}

export default StudentFilters;
