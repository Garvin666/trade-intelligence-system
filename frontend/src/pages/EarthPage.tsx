import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function EarthPage() {
  const navigate = useNavigate();

  return (
    <div className="earth-page" aria-label="3D 地球视角">
      <button
        type="button"
        className="earth-back-home"
        onClick={() => navigate("/")}
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        返回首页
      </button>
    </div>
  );
}
