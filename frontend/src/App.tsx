import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth, usePode } from "./contexto";
import Admin from "./pages/Admin";
import Importar from "./pages/Importar";
import LeadDetalhe from "./pages/LeadDetalhe";
import Leads from "./pages/Leads";
import { Login, RecuperarSenha, RedefinirSenha } from "./pages/Login";
import Painel from "./pages/Painel";
import Perfil from "./pages/Perfil";
import Relatorios from "./pages/Relatorios";
import Tarefas from "./pages/Tarefas";
import { Carregando } from "./ui";

export default function App() {
  const { usuario, carregando } = useAuth();
  const pode = usePode();
  const loc = useLocation();
  if (carregando) return <Carregando />;
  if (!usuario) {
    return (
      <Routes>
        <Route path="/recuperar-senha" element={<RecuperarSenha />} />
        <Route path="/redefinir-senha" element={<RedefinirSenha />} />
        <Route path="*" element={<Login destino={loc.pathname + loc.search} />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Painel />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/leads/:id" element={<LeadDetalhe />} />
        <Route path="/tarefas" element={<Tarefas />} />
        <Route path="/relatorios" element={<Relatorios />} />
        {pode.editar && <Route path="/importar" element={<Importar />} />}
        {pode.admin && <Route path="/admin" element={<Admin />} />}
        <Route path="/perfil" element={<Perfil />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
