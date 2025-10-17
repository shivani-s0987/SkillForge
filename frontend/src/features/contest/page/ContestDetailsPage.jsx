import React from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Calendar, Clock, Users, Award, CheckCircle } from "lucide-react";
import Header from "@/components/layout/Header";
import LoadingDotStream from "@/components/common/Loading";
import api from "@/services/api";
import useFetchContestDetails from "@/features/tutor/hooks/useFetchContestDetails";
import { displayToastAlert } from "@/utils/displayToastAlert";
import { useSelector } from "react-redux";
import Swal from "sweetalert2";
import { differenceInSeconds } from 'date-fns'

const ContestDetailsPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { contestDetails, error, loading } = useFetchContestDetails(id);
  const { user } = useSelector((state) => state.auth);

  if (!contestDetails | (contestDetails.length == 0)) {
    return;
  }

  const handleParticipate = async () => {
    try {
      if (!user) {
        console.log("not user found");
        displayToastAlert(100, 'Please login to continue...')
        return navigate("/login");
      }
      
      const res = await api.post(`contest/${id}/participate/`);
      console.log("res of res ====", res);
      if (res.status === 200) {
        await Swal.fire("Started", "Your time starts now", "success");
        navigate(`/contest/${id}/participate`);
      }
    } catch (error) {
      console.log(error);
      if (error.response?.status === 400) {
        displayToastAlert(400, error.response.data.error);
      }
    }
  };

  if (loading) return <LoadingDotStream />;
  if (error) return <div className="text-red-500 text-center">{error}</div>;

  return (
    <div className="bg-gradient-to-b from-emerald-100 to-white min-h-screen">
      <Header />
      <div className="max-w-7xl mx-auto pt-8 px-4">
        {contestDetails ? (
          <div className="bg-white rounded-xl  shadow-lg overflow-hidden">
            <div className="bg-gradient-to-r from-green-600 to-emerald-600 text-white p-6">
              <h1 className="text-3xl font-bold mb-2">{contestDetails.name}</h1>
              <p className="text-emerald-100">{contestDetails.description}</p>
            </div>
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-sm text-gray-600">AI Key Notes:</span>
                  <span className="ml-2 font-semibold text-sm text-indigo-600">{contestDetails.ai_summary_status || 'pending'}</span>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <InfoItem
                  icon={<Calendar className="w-5 h-5" />}
                  label="Start Time"
                  value={new Date(contestDetails.start_time).toLocaleString()}
                />
                <InfoItem
                  icon={<Clock className="w-5 h-5" />}
                  label="End Time"
                  value={new Date(contestDetails.end_time).toLocaleString()}
                />
                <InfoItem
                  icon={<Users className="w-5 h-5" />}
                  label="Total Questions"
                  value={contestDetails.total_questions}
                />
                <InfoItem
                  icon={<Award className="w-5 h-5" />}
                  label="Max Points"
                  value={contestDetails.max_points}
                />
              </div>

              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-3 text-emerald-800">
                  Contest Rules
                </h2>
                <ul className="space-y-2">
                  {[
                    "All questions are multiple choice.",
                    "Each correct answer awards points; no negative points for wrong answers.",
                    "Complete within the specified time limit.",
                    "Once submitted, answers cannot be changed.",
                    "Leaderboard rankings update in real-time.",
                    "Participants can only attempt once.",
                  ].map((rule, index) => (
                    <li key={index} className="flex items-start">
                      <CheckCircle className="w-5 h-5 text-emerald-500 mr-2 flex-shrink-0 mt-1" />
                      <span>{rule}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-3 text-emerald-800">
                  Top Participants
                </h2>
                <div className="bg-emerald-50 rounded-lg p-4">
                  {contestDetails &&
                    contestDetails?.leaderboard.map((participant, index) => (
                      <div
                        key={index}
                        className="flex justify-between items-center mb-2 last:mb-0"
                      >
                        <span className="font-semibold">
                          {participant.rank}. {participant?.user?.username}
                        </span>
                        <span className="bg-emerald-200 text-emerald-800 px-2 py-1 rounded">
                          {participant.score} points
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              {(contestDetails.status === "scheduled" ||
                contestDetails.status === "ongoing") && (
                <button
                  onClick={handleParticipate}
                  disabled={contestDetails.is_participated}
                  className={`w-full  bg-emerald-600 text-white px-6 py-3 rounded-lg shadow hover:bg-emerald-700 transition duration-300 ease-in-out transform hover:-translate-y-1`}
                >
                  {contestDetails.is_participated
                    ? "Completed"
                    : "Participate Now"}
                </button>
              )}
              {contestDetails.is_participated && (
                <div className="mt-4">
                  <button
                    onClick={() => navigate(`/summarized-keynotes?contest_id=${contestDetails.id}`)}
                    className="w-full bg-indigo-600 text-white px-6 py-3 rounded-lg shadow hover:bg-indigo-700 transition duration-300"
                  >
                    View AI Key Notes
                  </button>
                </div>
              )}

              {/* Tutor-only: Generate for all contests after contest end */}
              {user && (user.is_staff || user.role === 'tutor') && new Date(contestDetails.end_time) < new Date() && (
                <div className="mt-4">
                  <button
                    onClick={async () => {
                      const res = await Swal.fire({
                        title: 'Generate AI Key Notes for all contests?',
                        text: 'This will regenerate AI summaries for all contests. Continue?',
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: 'Yes, generate',
                      });
                      if (res.isConfirmed) {
                        try {
                          const resp = await api.post('summarizedkeynotes/generate_all/');
                          if (resp.status === 200) {
                            displayToastAlert(200, 'Generation started/completed for all contests');
                            // refresh contest details
                            window.location.reload();
                          }
                        } catch (err) {
                          console.error(err);
                          displayToastAlert(500, 'Failed to generate summaries for all contests');
                        }
                      }
                    }}
                    className="w-full bg-yellow-500 text-white px-6 py-3 rounded-lg shadow hover:bg-yellow-600 transition duration-300"
                  >
                    Generate AI Key Notes (All Contests)
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="text-center text-gray-600">
            No contest details available
          </p>
        )}
      </div>
    </div>
  );
};

const InfoItem = ({ icon, label, value }) => (
  <div className="flex items-center space-x-2">
    {icon}
    <span className="text-gray-600">{label}:</span>
    <span className="font-semibold">{value}</span>
  </div>
);

export default ContestDetailsPage;
