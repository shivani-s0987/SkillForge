import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '@/services/api';
import StudentCourseProgress from './StudentCourseProgress';
import StudentCharts from './StudentCharts';
import StudentContests from './StudentContests';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';

const StudentDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const fetchDetail = async () => {
    try {
      const res = await api.get(`api/students/${id}/analytics/`);
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchDetail(); }, [id]);

  if (loading) return <div className="p-6">Loading...</div>;

  if (!data) return <div className="p-6">No data</div>;

  const student = data.student;

  return (
    <motion.div initial={{opacity:0}} animate={{opacity:1}} className="p-6 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto">
        <button onClick={() => navigate(-1)} className="mb-4 inline-flex items-center text-indigo-600"><ArrowLeft className="mr-2" />Back</button>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-semibold text-indigo-700">{student.name}</h2>
              <div className="text-sm text-gray-500">{student.email}</div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-indigo-600">{data.performance?.average_score ?? '-'}</div>
              <div className="text-sm text-gray-500">Overall Score</div>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <StudentCharts data={data} />
            </div>

            <div className="bg-gray-50 p-4 rounded">
              <h4 className="font-semibold mb-3">Progress Summary</h4>
              <div className="space-y-2">
                <div>Completed: {data.performance.breakdown.completed}</div>
                <div>Ongoing: {data.performance.breakdown.ongoing}</div>
                <div>Not Started: {data.performance.breakdown.not_started}</div>
              </div>
            </div>
          </div>

          <div className="mt-6">
            <div className="flex items-center space-x-3 border-b pb-3">
              <button onClick={() => setActiveTab('overview')} className={`px-3 py-2 rounded ${activeTab==='overview' ? 'bg-indigo-600 text-white' : 'text-gray-600'}`}>Overview</button>
              <button onClick={() => setActiveTab('contests')} className={`px-3 py-2 rounded ${activeTab==='contests' ? 'bg-indigo-600 text-white' : 'text-gray-600'}`}>Contests & Tests</button>
            </div>

            <div className="mt-4">
              {activeTab === 'overview' && (
                <div>
                  <h3 className="font-semibold mb-3">Enrolled Courses</h3>
                  {data.courses.map(c => (
                    <StudentCourseProgress key={c.id} course={c} />
                  ))}
                </div>
              )}

              {activeTab === 'contests' && (
                <StudentContests contests={data.contests} summary={data.tests_summary} time_series={data.tests_time_series} />
              )}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default StudentDetail;
