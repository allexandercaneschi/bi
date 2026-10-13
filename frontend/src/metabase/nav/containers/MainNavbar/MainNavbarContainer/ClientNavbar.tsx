/**
 * ALL Tecnologias: menu lateral reduzido para usuários de "grupo de cliente".
 *
 * Mostra só o que o cliente pode usar: as pastas liberadas para ele e a lista de
 * painéis (dashboards) dessas pastas, para trocar de painel com um clique.
 * Sem Início, coleção pessoal, Dados, Lixeira, favoritos ou botões de criação.
 */
import _ from "underscore";

import ErrorBoundary from "metabase/ErrorBoundary";
import { useSearchQuery } from "metabase/api";
import type { CollectionTreeItem } from "metabase/common/collections/utils";
import { isRootPersonalCollection } from "metabase/common/collections/utils";
import { Tree } from "metabase/common/components/tree";
import * as Urls from "metabase/urls";
import type { DashboardId } from "metabase-types/api";

import {
  PaddedSidebarLink,
  SidebarContentRoot,
  SidebarHeading,
  SidebarSection,
} from "../MainNavbar.styled";
import { SidebarCollectionLink } from "../SidebarItems";

interface ClientNavbarProps {
  collections: CollectionTreeItem[];
  selectedCollectionId?: CollectionTreeItem["id"];
  selectedDashboardId?: DashboardId | string | number;
  onItemSelect: () => void;
}

export function ClientNavbar({
  collections,
  selectedCollectionId,
  selectedDashboardId,
  onItemSelect,
}: ClientNavbarProps) {
  const clientCollections = collections.filter(
    (collection) => !isRootPersonalCollection(collection),
  );

  const { data: dashboardResults } = useSearchQuery({
    models: ["dashboard"],
    filter_items_in_personal_collection: "exclude",
    context: "search-app",
  });

  const dashboards = _.sortBy(dashboardResults?.data ?? [], (dashboard) =>
    dashboard.name.toLowerCase(),
  );

  return (
    <ErrorBoundary>
      <SidebarContentRoot>
        <div>
          {dashboards.length > 0 && (
            <SidebarSection>
              <SidebarHeading>Painéis</SidebarHeading>
              {dashboards.map((dashboard) => (
                <PaddedSidebarLink
                  key={dashboard.id}
                  icon="dashboard"
                  url={Urls.dashboard({
                    id: Number(dashboard.id),
                    name: dashboard.name,
                  })}
                  isSelected={String(selectedDashboardId) === String(dashboard.id)}
                  onClick={onItemSelect}
                >
                  {dashboard.name}
                </PaddedSidebarLink>
              ))}
            </SidebarSection>
          )}

          {clientCollections.length > 0 && (
            <SidebarSection>
              <SidebarHeading>Pastas</SidebarHeading>
              <ErrorBoundary>
                <Tree
                  data={clientCollections}
                  selectedId={selectedCollectionId}
                  onSelect={onItemSelect}
                  TreeNode={SidebarCollectionLink}
                  role="tree"
                  aria-label="collection-tree"
                />
              </ErrorBoundary>
            </SidebarSection>
          )}
        </div>
      </SidebarContentRoot>
    </ErrorBoundary>
  );
}
