import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import Swal from "sweetalert2";

function CoursePage() {
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("purchase") === "success") {
      Swal.fire({
        title: "Course Purchase Successful!",
        text: "You can now access all your course materials.",
        icon: "success",
        confirmButtonText: "Start Learning",
      });
    }
  }, [location]);

  return <div>...course content...</div>;
}

export default CoursePage;
