(ns metabase.query-processor.middleware.all-client-scope
  "ALL Tecnologias: filtragem por cliente para perguntas SQL (fork do Metabase OSS).

  As perguntas usam marcadores no SQL, por exemplo `WHERE CLIENTE IN (__ALL_ERP__)`. Antes de as variáveis serem
  substituídas, este middleware troca cada marcador `__ALL_<CÓDIGO>__` pelo código do cliente:

  - **Usuário de grupo de cliente** (configuração `all-client-group-ids`, não administrador): usa sempre os códigos
    do próprio grupo. Qualquer valor enviado pelo navegador é ignorado. Marcadores de serviços que o grupo não
    contratou (ex.: auditoria) fazem a consulta falhar sem tocar no banco.
  - **Equipe da ALL** (qualquer outro usuário): usa o cliente escolhido na variável `{{all_cliente}}` (filtro
    \"Cliente\" do painel), pelo nome ou id do grupo. Serviços não contratados continuam visíveis para a equipe.
  - **Sem usuário** (link público, embed): a consulta falha.

  Os códigos ficam na configuração `all-client-group-config`, editada em Admin → Pessoas → Grupos.
  Nada é consultado se o SQL não tiver marcadores, então perguntas comuns não mudam."
  (:require
   [clojure.string :as str]
   [metabase.api.common :as api]
   [metabase.appearance.core :as appearance]
   [metabase.lib.parameters :as lib.parameters]
   [metabase.query-processor.error-type :as qp.error-type]
   [metabase.util :as u]
   [metabase.util.i18n :refer [tru]]
   [toucan2.core :as t2]))

(set! *warn-on-reflection* true)

(def client-tag-name
  "Nome da variável SQL usada pela equipe para escolher o cliente."
  "all_cliente")

(def ^:private token-pattern
  #"__ALL_([A-Z0-9]+(?:_[A-Z0-9]+)*)__")

(def ^:private client-tag-pattern
  #"\{\{\s*all_cliente\s*\}\}")

(def code->service
  "Códigos que pertencem a serviços contratados à parte. Os demais códigos são sempre liberados."
  {"wazuh" "auditoria"
   "squid" "navegacao"})

(def ^:private valid-code-value
  ;; letras (com acento), números, espaço e . , : _ - ; nada de aspas, ponto e vírgula ou comentários
  #"^[\p{L}\p{N} _.,:\-]{1,200}$")

;;; ------------------------------------------------ configuração -------------------------------------------------

(defn- ->id-string [k]
  (cond
    (keyword? k) (name k)
    :else        (str k)))

(defn- normalized-config*
  [raw]
  (into {}
        (for [[group-id cfg] raw
              :when (map? cfg)
              :let [get-any (fn [k] (or (get cfg k) (get cfg (keyword k))))]]
          [(->id-string group-id)
           {:codes    (into {}
                            (for [[k v] (get-any "codes")
                                  :let [v (some-> v str str/trim)]
                                  :when (not (str/blank? v))]
                              [(u/lower-case-en (->id-string k)) v]))
            :services (into {}
                            (for [[k v] (get-any "services")]
                              [(u/lower-case-en (->id-string k)) (true? v)]))}])))

(defn normalized-config
  "Configuração dos grupos no formato {\"<id>\" {:codes {\"erp\" \"6,7,23\"} :services {\"auditoria\" true}}}."
  []
  (normalized-config* (appearance/all-client-group-config)))

(defn client-group-ids
  "IDs (long) dos grupos marcados como grupo de cliente."
  []
  (into #{} (keep #(when (number? %) (long %))) (appearance/all-client-group-ids)))

(defn user-client-group-id
  "Se o usuário (não administrador) pertence a um grupo de cliente, devolve o id desse grupo."
  [user-id superuser?]
  (when (and user-id (not superuser?))
    (let [client-ids (client-group-ids)]
      (when (seq client-ids)
        (let [mine (into (sorted-set)
                         (filter client-ids)
                         (t2/select-fn-set :group_id :model/PermissionsGroupMembership :user_id user-id))]
          (when (> (count mine) 1)
            (throw (ex-info (tru "Usuário em mais de um grupo de cliente. Deixe-o em apenas um.")
                            {:type qp.error-type/bad-configuration})))
          (first mine))))))

(defn contracted-services
  "Serviços contratados pelo grupo de cliente (conjunto de strings)."
  [group-id]
  (let [services (get-in (normalized-config) [(->id-string group-id) :services])]
    (into (sorted-set) (keep (fn [[k v]] (when v k))) services)))

;;; ------------------------------------------------ query ---------------------------------------------------------

(defn- native-stages [query]
  (filter #(= (:lib/type %) :mbql.stage/native) (:stages query)))

(defn- client-tag? [tag]
  (= (:name tag) client-tag-name))

(defn- scoped-stage? [stage]
  (let [sql (:native stage)]
    (or (and (string? sql)
             (or (re-find token-pattern sql)
                 (re-find client-tag-pattern sql)))
        (some client-tag? (:template-tags stage)))))

(defn- client-tag-ids [query]
  (into #{client-tag-name}
        (comp (mapcat :template-tags)
              (filter client-tag?)
              (keep :id))
        (native-stages query)))

(defn- param-targets-client-tag? [tag-ids param]
  (when-let [target (:target param)]
    (contains? tag-ids (try
                         (lib.parameters/parameter-target-template-tag-name target)
                         (catch Throwable _ nil)))))

(defn- first-value [v]
  (let [v (if (sequential? v) (first v) v)]
    (when (some? v) (str/trim (str v)))))

(defn- selected-client
  "Valor escolhido pela equipe na variável `all_cliente` (parâmetro enviado ou valor padrão da variável)."
  [query tag-ids]
  (or (some (fn [param]
              (when (param-targets-client-tag? tag-ids param)
                (first-value (:value param))))
            (concat (:parameters query) (mapcat :parameters (:stages query))))
      (some (fn [tag] (when (client-tag? tag) (first-value (:default tag))))
            (mapcat :template-tags (native-stages query)))))

(defn resolve-group-name
  "Id (string) do grupo configurado cujo nome é `selected-lower` (já em minúsculas)."
  [selected-lower config]
  (let [ids (keep parse-long (keys config))]
    (when (seq ids)
      (some (fn [{:keys [id name]}]
              (when (= (u/lower-case-en (str/trim (str name))) selected-lower)
                (str id)))
            (t2/select [:model/PermissionsGroup :id :name] :id [:in ids])))))

(defn- resolve-staff-group-id
  [selected config]
  (when-not (str/blank? selected)
    (if (contains? config selected)
      selected
      (resolve-group-name (u/lower-case-en selected) config))))

(defn- replace-tokens
  [sql {:keys [codes services]} client? group-label]
  (str/replace sql token-pattern
               (fn [[_ token]]
                 (let [code    (u/lower-case-en token)
                       service (code->service code)
                       value   (get codes code)]
                   (when (and client? service (not (get services service)))
                     (throw (ex-info (tru "Serviço não contratado.")
                                     {:type                 qp.error-type/missing-required-permissions
                                      :all/service-blocked  service})))
                   (when (str/blank? value)
                     (throw (ex-info (tru "O código \"{0}\" não está configurado para o cliente {1}." code group-label)
                                     {:type qp.error-type/bad-configuration})))
                   (when-not (re-matches valid-code-value value)
                     (throw (ex-info (tru "O código \"{0}\" do cliente {1} tem caracteres não permitidos." code group-label)
                                     {:type qp.error-type/bad-configuration})))
                   value))))

(defn- rewrite-stage [stage group-cfg client? group-label]
  (if-not (= (:lib/type stage) :mbql.stage/native)
    stage
    (cond-> stage
      (string? (:native stage))
      (update :native (fn [sql]
                        (-> sql
                            (str/replace client-tag-pattern "")
                            (replace-tokens group-cfg client? group-label))))

      (:template-tags stage)
      (update :template-tags (fn [tags] (into [] (remove client-tag?) tags)))

      (:parameters stage)
      (update :parameters (fn [params]
                            (into [] (remove #(param-targets-client-tag? #{client-tag-name} %)) params))))))

(defn apply-client-scope
  "Middleware de pré-processamento (roda antes de `substitute-parameters`). Ver docstring do namespace."
  [query]
  (if-not (some scoped-stage? (native-stages query))
    query
    (let [user-id  api/*current-user-id*
          _        (when-not user-id
                     (throw (ex-info (tru "Esta pergunta só pode ser vista por usuários logados.")
                                     {:type qp.error-type/missing-required-permissions})))
          config   (normalized-config)
          tag-ids  (client-tag-ids query)
          client-group (user-client-group-id user-id api/*is-superuser?*)
          group-id (if client-group
                     (str client-group)
                     (or (resolve-staff-group-id (selected-client query tag-ids) config)
                         (throw (ex-info (tru "Selecione um cliente no filtro Cliente.")
                                         {:type qp.error-type/missing-required-parameter}))))
          group-cfg (or (get config group-id)
                        (throw (ex-info (tru "O grupo de cliente {0} ainda não tem códigos configurados." group-id)
                                        {:type qp.error-type/bad-configuration})))
          client?  (boolean client-group)
          tag-ids* (into tag-ids [client-tag-name])]
      (-> query
          (update :stages (fn [stages] (mapv #(rewrite-stage % group-cfg client? group-id) stages)))
          (cond-> (:parameters query)
            (update :parameters (fn [params] (into [] (remove #(param-targets-client-tag? tag-ids* %)) params))))))))
