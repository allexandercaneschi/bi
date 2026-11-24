import { t } from "ttag";
import { uniq } from "underscore";

import { Link } from "metabase/common/components/Link";
import { Sortable } from "metabase/common/components/Sortable";
import type { TabButtonMenuItem } from "metabase/common/components/TabButton";
import { TabButton } from "metabase/common/components/TabButton";
import { TabRow } from "metabase/common/components/TabRow";
import { useConfirmation } from "metabase/common/hooks/use-confirmation";
import CS from "metabase/css/core/index.css";
import { useDashboardContext } from "metabase/dashboard/context";
import { useRegisterShortcut } from "metabase/palette/hooks/useRegisterShortcut";
import type { SelectedTabId } from "metabase/redux/store";
import { ActionIcon, Flex, Icon, List } from "metabase/ui";
import { isVirtualDashCard } from "metabase/utils/dashboard";

import S from "./DashboardTabs.module.css";
import { useDashboardTabs } from "./use-dashboard-tabs";

/**
 * ALL Tecnologias: abas dentro de abas. Uma aba cujo nome tem o formato "Grupo › Sub-aba" vira uma sub-aba
 * do grupo "Grupo": a primeira linha mostra os grupos e, quando o grupo selecionado tem sub-abas, uma segunda
 * linha mostra só os nomes delas. Abas sem o separador continuam como sempre. Só vale na visualização;
 * na edição as abas aparecem planas, com o nome completo.
 */
const TAB_GROUP_SEPARATOR = " › ";

interface GroupedTab {
  id: number;
  label: string;
  isNested: boolean;
}

interface TabGroup {
  name: string;
  tabs: GroupedTab[];
}

function groupTabs(tabs: { id: number; name: string }[]): TabGroup[] {
  const groups: TabGroup[] = [];
  for (const tab of tabs) {
    const index = tab.name.indexOf(TAB_GROUP_SEPARATOR);
    const isNested = index >= 0;
    const groupName = isNested ? tab.name.slice(0, index) : tab.name;
    const label = isNested
      ? tab.name.slice(index + TAB_GROUP_SEPARATOR.length)
      : tab.name;
    let group = groups.find((g) => g.name === groupName);
    if (!group) {
      group = { name: groupName, tabs: [] };
      groups.push(group);
    }
    group.tabs.push({ id: tab.id, label, isNested });
  }
  return groups;
}

export function DashboardTabs() {
  const { isEditing = false, dashboard } = useDashboardContext();
  const { modalContent, show } = useConfirmation();

  const {
    tabs,
    createNewTab,
    duplicateTab,
    deleteTab,
    renameTab,
    selectTab,
    selectedTabId,
    moveTab,
  } = useDashboardTabs();
  const hasMultipleTabs = tabs.length > 1;
  const showTabs = hasMultipleTabs || isEditing;
  const showPlaceholder = tabs.length === 0 && isEditing;

  useRegisterShortcut(
    [
      {
        id: "dashboard-change-tab",
        perform: (_, event) => {
          if (!event?.key) {
            return;
          }
          const key = parseInt(event.key);
          const tab = tabs[key - 1];
          if (tab) {
            selectTab(tab.id);
          }
        },
      },
    ],
    [tabs],
  );

  if (!showTabs) {
    return null;
  }

  const menuItems: TabButtonMenuItem[] = [
    {
      label: t`Duplicate`,
      action: (_, value) => duplicateTab(value),
    },
  ];
  if (hasMultipleTabs) {
    menuItems.push({
      label: t`Delete`,
      action: (_, value) => {
        const performDelete = () => deleteTab(value);
        const tabQuestions = dashboard?.dashcards.filter(
          (dashcard) =>
            dashcard.dashboard_tab_id === value && !isVirtualDashCard(dashcard),
        );
        const tabDashboardQuestions = tabQuestions?.filter(
          (dashcard) => dashcard.card.dashboard_id !== null,
        );
        const hasDashboardQuestions = !!tabDashboardQuestions?.length;
        if (!hasDashboardQuestions) {
          performDelete();
          return;
        }
        const areAllDashboardQuestions =
          tabQuestions?.length === tabDashboardQuestions.length;
        show({
          size: areAllDashboardQuestions ? "sm" : undefined,
          title: areAllDashboardQuestions
            ? t`Delete this tab and its charts?`
            : t`Delete this tab?`,
          message: areAllDashboardQuestions ? (
            t`If you'd like to keep any of them, you can move them to a different tab, dashboard, or collection.`
          ) : (
            <>
              {t`This will also delete any questions saved in it. If you'd like to keep any of these, move them to a different tab, dashboard, or collection.`}
              <List ml="md" mt="sm">
                {uniq(tabDashboardQuestions, (dc) => dc.card.id).map(
                  (dashcard) => (
                    <List.Item key={dashcard.card.id}>
                      <Link
                        to={`/question/${dashcard.card.id}`}
                        className={CS.link}
                      >
                        {dashcard.card.name}
                      </Link>
                    </List.Item>
                  ),
                )}
              </List>
            </>
          ),
          confirmButtonText: t`Delete tab`,
          onConfirm: performDelete,
        });
      },
    });
  }

  const groups = isEditing ? [] : groupTabs(tabs);
  if (groups.some((group) => group.tabs.some((tab) => tab.isNested))) {
    const selectedGroup = groups.find((group) =>
      group.tabs.some((tab) => tab.id === selectedTabId),
    );
    const subTabs = selectedGroup?.tabs.some((tab) => tab.isNested)
      ? selectedGroup.tabs
      : [];
    return (
      <Flex direction="column" gap="xs" w="100%" className={S.dashboardTabs}>
        <TabRow<SelectedTabId>
          value={selectedGroup ? selectedGroup.tabs[0].id : selectedTabId}
          onChange={selectTab}
          itemIds={groups.map((group) => group.tabs[0].id)}
          handleDragEnd={moveTab}
        >
          {groups.map((group) => (
            <Sortable
              key={group.tabs[0].id}
              id={group.tabs[0].id}
              disabled
              role="presentation"
            >
              <TabButton.Renameable
                value={group.tabs[0].id}
                label={group.name}
                onRename={() => undefined}
                canRename={false}
                showMenu={false}
                menuItems={menuItems}
              />
            </Sortable>
          ))}
        </TabRow>
        {subTabs.length > 0 && (
          <TabRow<SelectedTabId>
            value={selectedTabId}
            onChange={selectTab}
            itemIds={subTabs.map((tab) => tab.id)}
            handleDragEnd={moveTab}
          >
            {subTabs.map((tab) => (
              <Sortable
                key={tab.id}
                id={tab.id}
                disabled
                role="presentation"
              >
                <TabButton.Renameable
                  value={tab.id}
                  label={tab.label}
                  onRename={() => undefined}
                  canRename={false}
                  showMenu={false}
                  menuItems={menuItems}
                />
              </Sortable>
            ))}
          </TabRow>
        )}
        {modalContent}
      </Flex>
    );
  }

  return (
    <Flex align="start" gap="lg" w="100%" className={S.dashboardTabs}>
      <TabRow<SelectedTabId>
        value={selectedTabId}
        onChange={selectTab}
        itemIds={tabs.map((tab) => tab.id)}
        handleDragEnd={moveTab}
      >
        {showPlaceholder ? (
          <TabButton
            label={t`Tab 1`}
            value={null}
            showMenu
            menuItems={menuItems}
          />
        ) : (
          tabs.map((tab) => (
            <Sortable
              key={tab.id}
              id={tab.id}
              disabled={!isEditing}
              role="presentation"
            >
              <TabButton.Renameable
                value={tab.id}
                label={tab.name}
                onRename={(name) => renameTab(tab.id, name)}
                canRename={isEditing && hasMultipleTabs}
                showMenu={isEditing}
                menuItems={menuItems}
              />
            </Sortable>
          ))
        )}
        {isEditing && (
          <ActionIcon
            variant="viewHeader"
            onClick={createNewTab}
            aria-label={t`Create new tab`}
            className={S.createTabButton}
          >
            <Icon name="add" size={12} />
          </ActionIcon>
        )}
      </TabRow>
      {modalContent}
    </Flex>
  );
}
