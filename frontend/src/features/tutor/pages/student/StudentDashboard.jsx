import React, { useEffect, useState } from 'react';
import api from '@/services/api';
import StudentCard from './StudentCard';
import StudentChart from './StudentChart';
import StudentFilters from './StudentFilters';
import { motion } from 'framer-motion';

const StudentDashboard = () => {
  const [data, setData] = useState({students: [], aggregated: {}, time_series: {}});
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const res = await api.get('student-analytics/');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30000); // auto-refresh every 30s
    return () => clearInterval(iv);
  }, []);

  return (
    <motion.div initial={{opacity:0, y:10}} animate={{opacity:1, y:0}} className="p-6 bg-gray-50 min-h-screen">
      <div className="max-w-7xl mx-auto">
        <h2 className="text-2xl font-semibold text-indigo-700">Student Analytics</h2>
        <p className="text-sm text-gray-500">Real-time student performance and course insights</p>

        <StudentFilters />

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mt-6">
          <div className="col-span-1 bg-white p-4 rounded-lg shadow">
            <h3 className="text-sm text-gray-500">Total Students</h3>
            <div className="text-3xl font-bold text-indigo-600">{data.aggregated?.total_students ?? '-'}</div>
          </div>
          <div className="col-span-1 bg-white p-4 rounded-lg shadow">
            <h3 className="text-sm text-gray-500">Average Score</h3>
            <div className="text-3xl font-bold text-indigo-600">{data.aggregated?.average_score ?? '-'}</div>
          </div>
          <div className="col-span-1 bg-white p-4 rounded-lg shadow">
            <h3 className="text-sm text-gray-500">Top Performer</h3>
            <div className="text-lg font-semibold">{data.aggregated?.top_performers?.[0]?.user__username ?? '-'}</div>
          </div>
          <div className="col-span-1 bg-white p-4 rounded-lg shadow">
            <h3 className="text-sm text-gray-500">Avg Completion %</h3>
            <div className="text-3xl font-bold text-indigo-600">{data.aggregated?.average_score ? (Math.round(data.aggregated.average_score)) : '-'}</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow">
            <StudentChart data={data.time_series} />
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-4">Top Students</h3>
            {loading ? <div>Loading...</div> : (
              data.students.slice(0,6).map(s => (
                <StudentCard key={s.id} student={s} />
              ))
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default StudentDashboard;
