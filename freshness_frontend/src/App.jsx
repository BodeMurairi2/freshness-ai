import { BrowserRouter, Link, Route, Routes } from "react-router";
import { AuthProvider } from "./auth/AuthContext";
import Layout from "./components/Layout";
import RequireLogin from "./components/RequireLogin";
import PredictPage from "./pages/PredictPage";
import RetrainPage from "./pages/RetrainPage";
import ModelsPage from "./pages/ModelsPage";
import InsightsPage from "./pages/InsightsPage";
import { LoginPage, PasswordPage, RegisterPage } from "./pages/AuthPages";

function NotFound() {
  return (
    <main className="page">
      <div className="card empty stack" style={{ alignItems: "center" }}>
        <h2>Page not found</h2>
        <Link className="button primary" to="/">Check a fruit</Link>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<PredictPage />} />
            <Route path="retrain" element={<RequireLogin title="retrain the model"><RetrainPage /></RequireLogin>} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="insights" element={<InsightsPage />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="register" element={<RegisterPage />} />
            <Route path="password" element={<PasswordPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
