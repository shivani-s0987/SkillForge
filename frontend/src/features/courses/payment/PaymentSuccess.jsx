import React, { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "../../../services/api"; // Your Axios instance
import { displayToastAlert } from "../../../utils/displayToastAlert"; // Custom toast utility

const PaymentSuccess = () => {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const courseSlug = params.get("course_id");
    const userID = params.get("user_id");
    const accessType = params.get("access_type");
    const sessionID = params.get("session_id");

    const confirmCoursePurchase = async () => {
      try {
        const response = await api.post("/api/payments/payment-success/", {
          course_id: courseSlug,
          user_id: userID,
          access_type: accessType,
          session_id: sessionID,
        });

        console.log("✅ Payment Success Response:", response.data);
        displayToastAlert(200, "🎉 Your course purchase was successful!");

        // Delay navigation slightly for UX
        setTimeout(() => {
          navigate(`/course/${courseSlug}`, { state: { showConfetti: true } });
        }, 1500);
      } catch (error) {
        console.error("❌ Payment confirmation failed:", error.response?.data || error.message);
        displayToastAlert(400, "Payment confirmation failed. Please contact support.");
        navigate("/courses");
      }
    };

    // Validate query params before confirming payment
    if (courseSlug && userID && accessType && sessionID) {
      confirmCoursePurchase();
    } else {
      displayToastAlert(400, "Invalid payment confirmation URL.");
      navigate("/courses");
    }
  }, [location, navigate]);

  return (
    <div
      style={{
        height: "100vh",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(135deg, #007bff 0%, #6610f2 100%)",
        color: "white",
        textAlign: "center",
      }}
    >
      <h2 style={{ fontSize: "2rem", fontWeight: "600" }}>Processing your payment...</h2>
      <p style={{ fontSize: "1.1rem", marginTop: "10px", opacity: "0.9" }}>
        Please wait while we confirm your purchase securely.
      </p>
      <div
        className="loader"
        style={{
          marginTop: "30px",
          width: "40px",
          height: "40px",
          border: "4px solid rgba(255, 255, 255, 0.3)",
          borderTop: "4px solid #fff",
          borderRadius: "50%",
          animation: "spin 1s linear infinite",
        }}
      />
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  );
};

export default PaymentSuccess;
