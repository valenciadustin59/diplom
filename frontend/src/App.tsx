import { useEffect } from "react";
import {
  Navigate,
  Route,
  Routes,
  matchPath,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { AuditWorkspace, EmptyWorkspace } from "./components/AuditWorkspace";
import { ControlRail } from "./components/ControlRail";
import { useAuditWorkspace } from "./hooks/useAuditWorkspace";
import type { AuditCreatePayload, AuditTab } from "./types";

const validTabs: AuditTab[] = ["overview", "pages", "competitors", "recommendations"];

type AuditWorkspaceRouteProps = ReturnType<typeof useAuditWorkspace>;

function getActiveTab(value: string | null): AuditTab {
  if (value && validTabs.includes(value as AuditTab)) {
    return value as AuditTab;
  }
  return "overview";
}

function AuditWorkspaceRoute(props: AuditWorkspaceRouteProps) {
  const { auditId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = getActiveTab(searchParams.get("tab"));
  const { selectAudit, selectedAuditId } = props;

  useEffect(() => {
    if (auditId && auditId !== selectedAuditId) {
      selectAudit(auditId);
    }
  }, [auditId, selectAudit, selectedAuditId]);

  if (!auditId) {
    return <Navigate to="/" replace />;
  }

  return (
    <AuditWorkspace
      currentAudit={props.currentAudit}
      currentResults={props.currentResults}
      recommendations={props.recommendations}
      pageRows={props.pageRows}
      competitorScores={props.competitorScores}
      comparisonSummary={props.comparisonSummary}
      auditStatus={props.auditStatus}
      loading={props.loadingAudit}
      error={props.workspaceError}
      activeTab={activeTab}
      onTabChange={(tab) => setSearchParams({ tab })}
    />
  );
}

function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workspace = useAuditWorkspace();
  const activeMatch = matchPath("/audits/:auditId", location.pathname);
  const activeAuditId = activeMatch?.params.auditId ?? null;
  const homeView = searchParams.get("view") === "history" ? "history" : "new";

  async function handleCreateAudit(payload: AuditCreatePayload): Promise<boolean> {
    const audit = await workspace.createAudit(payload);
    if (!audit) {
      return false;
    }

    navigate(`/audits/${audit.id}?tab=overview`);
    return true;
  }

  function handleSelectAudit(auditId: string) {
    workspace.selectAudit(auditId);
    navigate(`/audits/${auditId}?tab=overview`);
  }

  return (
    <div className="app-shell">
      <div className="app-shell__backdrop app-shell__backdrop--left" />
      <div className="app-shell__backdrop app-shell__backdrop--right" />

      <ControlRail
        activeView={activeAuditId ? "history" : homeView}
        onOpenNew={() => navigate("/?view=new")}
        onOpenHistory={() => navigate("/?view=history")}
      />

      <main className="content">
        <div className="content__inner">
          <Routes>
            <Route
              path="/"
              element={
                <EmptyWorkspace
                  mode={homeView}
                  recentAudits={workspace.recentAudits}
                  activeAuditId={activeAuditId}
                  loadingRecent={workspace.loadingRecent}
                  submitting={workspace.submitting}
                  submissionError={workspace.submissionError}
                  success={workspace.success}
                  onCreateAudit={handleCreateAudit}
                  onSelectAudit={handleSelectAudit}
                />
              }
            />
            <Route path="/audits/:auditId" element={<AuditWorkspaceRoute {...workspace} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return <AppShell />;
}
