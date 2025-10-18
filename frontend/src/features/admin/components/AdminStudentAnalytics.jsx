import React, { useEffect, useState } from 'react';
import api from '@/services/api';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import useAdminStudentAnalytics from '../hooks/useAdminStudentAnalytics';

const AdminStudentAnalytics = ({ studentId, onClose }) => {
  const { data, connected, send } = useAdminStudentAnalytics(studentId);
  const [loading, setLoading] = useState(true);
  const [localData, setLocalData] = useState(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      try {
        const res = await api.get(`admin/students/${studentId}/analytics/`);
        if (mounted) setLocalData(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchData();

    return () => { mounted = false };
  }, [studentId]);

  useEffect(() => {
    if (data) {
      setLocalData(data);
    }
  }, [data]);

  if (loading || !localData) return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded shadow w-11/12 md:w-3/4 lg:w-2/3">Loading...</div>
    </div>
  );

  const { name, email, joined_date, last_login, status, courses, contests, summary } = localData;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <motion.div initial={{y:20, opacity:0}} animate={{y:0, opacity:1}} exit={{y:20, opacity:0}} className="bg-white rounded-lg shadow-lg w-11/12 md:w-4/5 lg:w-3/4 max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <h3 className="text-lg font-semibold text-indigo-700">{name}</h3>
            <div className="text-sm text-gray-500">{email}</div>
          </div>
          <div className="flex items-center space-x-3">
            <div className={`px-3 py-1 rounded text-white ${status === 'Active' ? 'bg-green-500' : 'bg-red-500'}`}>{status}</div>
            <button onClick={onClose} className="p-2 rounded hover:bg-gray-100"><X /></button>
          </div>
        </div>

        <div className="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            {/* Summary cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <div className="bg-indigo-50 p-4 rounded">
                <div className="text-sm text-gray-500">Total Tests</div>
                <div className="text-2xl font-bold text-indigo-600">{summary.total_tests}</div>
              </div>
              <div className="bg-indigo-50 p-4 rounded">
                <div className="text-sm text-gray-500">Attempted</div>
                <div className="text-2xl font-bold text-indigo-600">{summary.attempted}</div>
              </div>
              <div className="bg-indigo-50 p-4 rounded">
                <div className="text-sm text-gray-500">Average Score</div>
                <div className="text-2xl font-bold text-indigo-600">{summary.average_score}</div>
              </div>
            </div>

            {/* Contests table */}
            <div className="bg-white border rounded">
              <table className="min-w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Title</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Date</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Max Marks</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Student Marks</th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500">Attendance</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Rank</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Progress</th>
                  </tr>
                </thead>
                <tbody>
                  {contests.map(ct => (
                    <tr key={ct.id} className={`${ct.attendance_status === 'Absent' ? 'bg-red-50 text-gray-400' : ''}`}>
                      <td className="px-4 py-3 text-sm">{ct.title}</td>
                      <td className="px-4 py-3 text-sm">{new Date(ct.date_conducted).toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm text-right">{ct.max_marks}</td>
                      <td className={`px-4 py-3 text-sm text-right ${ct.attendance_status==='Absent' ? 'text-gray-400' : 'text-indigo-600'}`}>{ct.student_marks}</td>
                      <td className="px-4 py-3 text-center"><span className={`px-2 py-1 rounded text-xs ${ct.attendance_status==='Absent' ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'}`}>{ct.attendance_status}</span></td>
                      <td className="px-4 py-3 text-sm text-right">{ct.rank ?? '-'}</td>
                      <td className="px-4 py-3 text-sm text-right">{ct.progress_percentage}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            {/* Right column - charts & block control */}
            <div className="bg-white p-4 rounded mb-4">
              <h4 className="text-sm text-gray-500">Attendance %</h4>
              <div className="text-2xl font-bold text-indigo-600">{summary.attendance_percentage}%</div>
            </div>
            <div className="bg-white p-4 rounded">
              <h4 className="text-sm text-gray-500">Best Rank</h4>
              <div className="text-2xl font-bold text-indigo-600">{summary.best_rank ?? '-'}</div>
            </div>

            <div className="mt-4 flex justify-end">
              <button onClick={async () => {
                // optimistic toggle
                const newState = !(status === 'Active');
                try {
                  // send API to toggle
                  await api.patch(`admin/students/${studentId}/block/`, { is_active: newState });
                  // reflect change locally
                  localData.status = newState ? 'Active' : 'Blocked';
                } catch (err) { console.error(err) }
              }} className={`mt-4 w-full bg-red-500 hover:bg-red-600 text-white py-2 rounded`}>Block</button>
            </div>
          </div>
        </div>

      </motion.div>
    </div>
  )
}

export default AdminStudentAnalytics;
