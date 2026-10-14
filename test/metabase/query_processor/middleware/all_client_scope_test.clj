(ns metabase.query-processor.middleware.all-client-scope-test
  (:require
   [clojure.test :refer :all]
   [metabase.api.common :as api]
   [metabase.query-processor.middleware.all-client-scope :as all-client-scope]))

(def ^:private config
  {:12 {:codes    {:erp "6,7,23" :zabbix "30" :tactical "Tecmar" :wazuh "cli_tecmar"}
        :services {:auditoria false :navegacao false}}
   :13 {:codes    {:erp "40" :wazuh "cli_outro"}
        :services {:auditoria true}}})

(defn- native-query [sql & {:keys [tags parameters]}]
  (cond-> {:lib/type :mbql/query
           :database 1
           :stages   [{:lib/type      :mbql.stage/native
                       :native        sql
                       :template-tags (vec tags)}]}
    parameters (assoc :parameters parameters)))

(def ^:private client-tag
  {:name "all_cliente" :display-name "Cliente" :type :text :id "tag-1"})

(defn- client-param [value]
  {:type :category :value value :target [:variable [:template-tag "all_cliente"]]})

(defn- scope! [query & {:keys [user-id superuser? client-group]}]
  (binding [api/*current-user-id* user-id
            api/*is-superuser?*   (boolean superuser?)]
    (with-redefs [all-client-scope/normalized-config     (fn
                                                           ([] (#'all-client-scope/normalized-config* config))
                                                           ([raw] (#'all-client-scope/normalized-config* raw)))
                  all-client-scope/user-client-group-id  (fn [_ _] client-group)
                  all-client-scope/resolve-group-name    (fn [selected _config]
                                                           ({"grupo tecmar" "12" "outro" "13"} selected))]
      (all-client-scope/apply-client-scope query))))

(defn- sql-of [query]
  (get-in query [:stages 0 :native]))

(deftest no-markers-test
  (testing "perguntas sem marcadores passam sem mudança, mesmo sem usuário"
    (let [q (native-query "SELECT 1")]
      (is (= q (scope! q))))))

(deftest client-user-test
  (testing "usuário de cliente usa os códigos do próprio grupo e ignora o filtro enviado"
    (let [q (native-query "SELECT * FROM A WHERE C IN (__ALL_ERP__) /* {{all_cliente}} */"
                          :tags [client-tag]
                          :parameters [(client-param "Outro")])
          r (scope! q :user-id 5 :client-group 12)]
      (is (= "SELECT * FROM A WHERE C IN (6,7,23) /*  */" (sql-of r)))
      (is (empty? (get-in r [:stages 0 :template-tags])))
      (is (empty? (:parameters r)))))
  (testing "serviço não contratado bloqueia para o cliente"
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"não contratado"
                          (scope! (native-query "SELECT * FROM __ALL_WAZUH__.eventos") :user-id 5 :client-group 12))))
  (testing "serviço contratado libera"
    (is (= "SELECT * FROM cli_outro.eventos"
           (sql-of (scope! (native-query "SELECT * FROM __ALL_WAZUH__.eventos") :user-id 5 :client-group 13))))))

(deftest staff-user-test
  (testing "equipe escolhe o cliente pelo filtro e vê serviços não contratados"
    (let [q (native-query "SELECT * FROM __ALL_WAZUH__.e WHERE g = __ALL_ZABBIX__ /* {{all_cliente}} */"
                          :tags [client-tag]
                          :parameters [(client-param ["Grupo Tecmar"])])]
      (is (= "SELECT * FROM cli_tecmar.e WHERE g = 30 /*  */"
             (sql-of (scope! q :user-id 1 :superuser? true))))))
  (testing "valor padrão da variável é usado quando nada é enviado"
    (let [q (native-query "SELECT __ALL_ERP__ /* {{all_cliente}} */"
                          :tags [(assoc client-tag :default "Outro")])]
      (is (= "SELECT 40 /*  */" (sql-of (scope! q :user-id 1))))))
  (testing "sem cliente escolhido a consulta falha"
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"Selecione um cliente"
                          (scope! (native-query "SELECT __ALL_ERP__") :user-id 1)))))

(deftest fail-closed-test
  (testing "sem usuário (link público) a consulta falha"
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"usuários logados"
                          (scope! (native-query "SELECT __ALL_ERP__") :user-id nil))))
  (testing "código não configurado falha"
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"não está configurado"
                          (scope! (native-query "SELECT __ALL_BACULA__") :user-id 5 :client-group 12))))
  (testing "nomes de grupo do Zabbix com barra são aceitos"
    (is (= "SELECT 'Clientes/Tecmar'"
           (binding [api/*current-user-id* 5]
             (with-redefs [all-client-scope/normalized-config    (fn [& _] {"12" {:codes {"zabbix" "Clientes/Tecmar"} :services {}}})
                           all-client-scope/user-client-group-id (fn [_ _] 12)]
               (get-in (all-client-scope/apply-client-scope (native-query "SELECT '__ALL_ZABBIX__'"))
                       [:stages 0 :native]))))))
  (testing "comentário SQL (--) é recusado"
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"não permitidos"
                          (binding [api/*current-user-id* 5]
                            (with-redefs [all-client-scope/normalized-config    (fn [& _] {"12" {:codes {"erp" "6 -- x"} :services {}}})
                                          all-client-scope/user-client-group-id (fn [_ _] 12)]
                              (all-client-scope/apply-client-scope (native-query "SELECT __ALL_ERP__")))))))
  (testing "valores com aspas ou ponto e vírgula são recusados"
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"não permitidos"
                          (binding [api/*current-user-id* 5]
                            (with-redefs [all-client-scope/normalized-config    (fn [& _] {"12" {:codes {"erp" "1); DROP TABLE x;--"} :services {}}})
                                          all-client-scope/user-client-group-id (fn [_ _] 12)]
                              (all-client-scope/apply-client-scope (native-query "SELECT __ALL_ERP__"))))))))

(deftest normalized-config-test
  (is (= {"12" {:codes {"erp" "6,7,23" "zabbix" "30" "tactical" "Tecmar" "wazuh" "cli_tecmar"}
                :services {"auditoria" false "navegacao" false}}
          "13" {:codes {"erp" "40" "wazuh" "cli_outro"} :services {"auditoria" true}}}
         (#'all-client-scope/normalized-config* config))))
