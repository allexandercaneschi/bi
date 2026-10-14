import { useCallback, useMemo } from "react";
import { t } from "ttag";

import { getServiceForTabName } from "metabase/branding/client-services";
import { useDashboardContext } from "metabase/dashboard/context";
import { useSelector } from "metabase/redux";
import {
  canUserCreateNativeQueries,
  canUserCreateQueries,
  getAllClientServices,
  getIsAllClientUser,
} from "metabase/selectors/user";
import { Loader } from "metabase/ui";
import type { DashboardCard } from "metabase-types/api";

import {
  DashboardGridConnected,
  type DashboardGridProps,
} from "../../DashboardGrid";
import {
  DashboardEmptyState,
  DashboardEmptyStateWithoutAddPrompt,
} from "../DashboardEmptyState/DashboardEmptyState";

import { ServicePreview } from "./ServicePreview/ServicePreview";

export const Grid = ({
  className,
  style,
  p,
}: Pick<DashboardGridProps, "className" | "style" | "p">) => {
  const {
    dashboard,
    selectedTabId,
    isEditing,
    onRefreshPeriodChange,
    isLoadingWithoutCards,
    onAddQuestion,
    isEditableDashboard,
  } = useDashboardContext();

  const currentTabDashcards = useMemo(() => {
    if (!dashboard || !Array.isArray(dashboard.dashcards)) {
      return [];
    }
    if (!selectedTabId) {
      return dashboard.dashcards;
    }
    return dashboard.dashcards.filter(
      (dc: DashboardCard) => dc.dashboard_tab_id === selectedTabId,
    );
  }, [dashboard, selectedTabId]);
  const tabHasCards = currentTabDashcards.length > 0;
  const dashboardHasCards = dashboard && dashboard.dashcards.length > 0;

  /**
   * In the original code before (metabase#59529), we render `DashboardEmptyStateWithoutAddPrompt` directly
   * inside `PublicOrEmbeddedDashboardView` and this component doesn't need to check conditions that relies
   * on `GET /api/database`. After the consolidation every dashboard uses the same component, so we probably
   * missed this case.
   */
  const hasDataAccess = useSelector(canUserCreateQueries);
  const hasNativeWrite = useSelector(canUserCreateNativeQueries);
  const canCreateQuestions = hasDataAccess || hasNativeWrite;

  const handleSetEditing = useCallback(() => {
    if (!isEditing) {
      onRefreshPeriodChange(null);
    }
  }, [isEditing, onRefreshPeriodChange]);

  const handleAddQuestion = useCallback(() => {
    handleSetEditing();
    onAddQuestion?.(dashboard);
  }, [handleSetEditing, dashboard, onAddQuestion]);

  const isEmpty = !dashboardHasCards || (dashboardHasCards && !tabHasCards);

  // ALL Tecnologias: aba de serviço que o grupo do cliente não contratou → prévia desfocada + convite
  const isAllClientUser = useSelector(getIsAllClientUser);
  const allClientServices = useSelector(getAllClientServices);
  const selectedTab = dashboard?.tabs?.find((tab) => tab.id === selectedTabId);
  const tabService = getServiceForTabName(selectedTab?.name);
  const isServiceLocked =
    isAllClientUser &&
    !isEditing &&
    tabService != null &&
    !allClientServices.includes(tabService.key);

  if (isServiceLocked && tabService) {
    return <ServicePreview service={tabService} />;
  }

  if (isLoadingWithoutCards) {
    return <Loader size="lg" label={t`Loading…`} />;
  }

  if (isEmpty) {
    if (!dashboardHasCards) {
      return isEditableDashboard ? (
        <DashboardEmptyState
          canCreateQuestions={canCreateQuestions}
          addQuestion={handleAddQuestion}
          isDashboardEmpty={true}
          isEditing={isEditing}
        />
      ) : (
        <DashboardEmptyStateWithoutAddPrompt isDashboardEmpty={true} />
      );
    }

    if (dashboardHasCards && !tabHasCards) {
      return isEditableDashboard ? (
        <DashboardEmptyState
          canCreateQuestions={canCreateQuestions}
          addQuestion={handleAddQuestion}
          isDashboardEmpty={false}
          isEditing={isEditing}
        />
      ) : (
        <DashboardEmptyStateWithoutAddPrompt isDashboardEmpty={false} />
      );
    }
  }

  return (
    <DashboardGridConnected
      handleSetEditing={handleSetEditing}
      className={className}
      style={style}
      p={p}
    />
  );
};
