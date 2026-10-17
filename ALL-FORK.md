# Portal BI — ALL Tecnologias (fork do Metabase OSS)

Fork do [Metabase](https://github.com/metabase/metabase) open source (AGPL-3.0) com a identidade
visual da ALL Tecnologias. **Nenhum código da pasta `enterprise/` é usado ou alterado.**

Base atual: `v0.63.18.4` · Branch: `all-branding`

## O que foi alterado

| O quê | Onde editar |
|---|---|
| Nome "B.I ALL Tecnologias" na interface, mensagens de carregamento, links do metabase.com ocultos | `frontend/src/metabase/branding/config.ts` |
| Nome no título da aba/e-mails, **cores da marca**, logo padrão | `src/metabase/appearance/settings.clj` (valores `:default`) |
| **Tema escuro** com a paleta unificada do design system ALL Tecnologias (fundos, textos, semáforo) | `frontend/src/metabase/ui/colors/constants/themes/dark.ts` (bloco `ALL_DARK`) |
| Tema escuro como padrão para todos os usuários (cada um ainda pode trocar no perfil) | `src/metabase/users/settings.clj` (`color-scheme`) |
| Fonte da interface: Inter | `src/metabase/appearance/settings.clj` (`application-font`) |
| Logo da barra superior (horizontal: ícone + "ALL Tecnologias") | `resources/frontend_client/app/assets/img/all-logo-horizontal.svg` |
| Ícone (login, admin, menus) | `resources/frontend_client/app/assets/img/all-logo-icon.svg` |
| Favicon | `resources/frontend_client/app/assets/img/favicon.ico` (+ `favicon-16x16.png`, `favicon-32x32.png`) |
| Logo dos e-mails (assinaturas de dashboard) | `resources/frontend_client/app/assets/img/email_logo.png` |

Arquivos de apoio: `.github/workflows/all-build.yml` (build da imagem), `bin/all-upgrade.sh` (atualização de versão).

> Logos e favicon gerados a partir dos arquivos oficiais do design system (ícone e logo texto, sem o slogan na barra); cor da marca `#35A8E0`. Para trocar, mantenha os mesmos nomes de arquivo.

### Como funciona (resumo técnico)
As configurações de aparência do Metabase (`application-name`, `application-colors`,
`application-logo-url`) existem no código AGPL, mas sem licença paga o backend sempre devolve o
**valor padrão**. O fork só troca esses padrões e os seletores OSS do frontend — o gate de licença
não é removido nem contornado.

### O que NÃO foi alterado (de propósito)
- **Selo "Powered by Metabase" nos embeds estáticos** (`frontend/src/metabase/embedding/components/LogoBadge/`).
  A licença de embedding do Metabase isenta sua aplicação da AGPL *desde que o selo permaneça*.
  Remover é permitido pela AGPL neste fork, mas aí sua aplicação que embute os painéis perde essa isenção.
  Decida com calma antes de mexer.
- Selo "Made with Metabase" nos PDFs exportados (`src/metabase/channel/render/pdf.clj`) — pode ser
  removido depois, se quiser.
- Testes do upstream que esperam o texto "Metabase" não foram ajustados (o build de produção não os roda).

## Design system ALL Tecnologias

- Tema **escuro por padrão** (`color-scheme` = `dark` em `src/metabase/users/settings.clj`; cada usuário ainda pode trocar no perfil).
- Paleta escura em `frontend/src/metabase/ui/colors/constants/themes/dark.ts`, bloco `ALL_DARK`
  (surface-0/100/200, border, ink, ink-muted, brand-strong, brand-soft, semáforo, texto escuro sobre o azul).
- Fonte de interface **Inter** (padrão de `application-font`).

## Grupos de cliente (interface reduzida)

Em **Admin → Pessoas → Grupos → (grupo)** há o interruptor **"Grupo de cliente"**. Membros desses
grupos (que não sejam administradores) veem apenas as coleções liberadas para eles:

- o menu lateral mostra só **Painéis** (todos os dashboards liberados) e **Pastas** (coleções
  liberadas), e fica sempre aberto (não recolhe ao abrir um painel);
- somem o botão **Novo**, o **Metabot**, **Início**, **Sua coleção pessoal**, a seção **Dados**
  (bancos, modelos, métricas), **Lixeira** e favoritos;
- ao abrir o portal (ou clicar no logo) vão direto para a primeira coleção liberada.
- Código: `MainNavbarContainer/ClientNavbar.tsx`.

Os grupos marcados ficam na configuração `all-client-group-ids`. Isso só muda a interface: o acesso
real aos dados continua definido em **Admin → Permissões** (Dados: sem acesso; Coleções: só
visualização da pasta do cliente).

## Build

O GitHub Actions gera a imagem automaticamente a cada push no branch `all-branding`
(ou manualmente em **Actions → Build ALL Portal BI → Run workflow**). O build leva ~40–90 min.

Tags geradas em `ghcr.io/<seu-usuario>/portal-bi`:
- `v0.63.18.4-all.<N>` — uma por build (N = número da execução); use esta no Portainer
- `v0.63.18.4-all` e `latest` — sempre o build mais recente

Local (máquina com 8+ GB de RAM livres):
```bash
docker build --build-arg MB_EDITION=oss --build-arg VERSION=v0.63.18.4-all.0 -t portal-bi:local .
```

## Produção atual (servidor Docker)

Container avulso `Metabase`, porta 3000, banco de aplicação no **PostgreSQL 18** (variáveis `MB_DB_*`).
**Drivers extras** (ex.: **Firebird** do ERP) ficam em `/root/metabase-plugins` no servidor e
precisam ser montados em `/plugins`; sem isso os bancos Firebird param de funcionar.
O Metabase roda no container com o usuário **2000**, então a pasta precisa pertencer a ele:
`chown -R 2000:2000 /root/metabase-plugins` (senão ele ignora a pasta e o driver não carrega).

```bash
BK=$(cat /root/.ultimo-backup-metabase)          # pasta com metabase.env e o último backup
IMG=ghcr.io/allexandercaneschi/portal-bi:v0.63.18.4-all.<N>
# backup (cliente do Postgres na MESMA versão do servidor: 18)
set -a; . $BK/metabase.env; set +a
docker run --rm -e PGPASSWORD="$MB_DB_PASS" -v $BK:/bk postgres:18 \
  pg_dump -h "$MB_DB_HOST" -p "${MB_DB_PORT:-5432}" -U "$MB_DB_USER" -d "$MB_DB_DBNAME" -Fc -f /bk/metabase.dump
# troca
docker pull $IMG
docker rm -f Metabase
docker run -d --name Metabase --restart always -p 3000:3000 \
  -v /root/metabase-plugins:/plugins --env-file $BK/metabase.env $IMG
```

## Deploy no Portainer

Troque só a imagem da stack atual; o banco de aplicação (Postgres/H2) continua o mesmo.

```yaml
services:
  metabase:
    image: ghcr.io/<seu-usuario>/portal-bi:v0.63.18.4-all.<N>
    # ...mantenha environment, volumes e portas que você já usa
```

Depois do primeiro start:
1. **Admin → Configurações → Geral → Nome do site**: troque para "B.I ALL Tecnologias" (o valor antigo
   fica salvo no banco e tem prioridade sobre o padrão do fork).
2. Confirme a **URL do site** — o logo dos e-mails depende dela.
3. Faça backup do banco antes de trocar a imagem, como em qualquer upgrade.

## Atualizar para uma nova versão do Metabase

```bash
bin/all-upgrade.sh v0.63.18.4 v0.64.1
# edite BASE_VERSION em .github/workflows/all-build.yml para v0.64.1 e faça commit
git push --force-with-lease origin all-branding   # dispara o build
```

## Licença (AGPL-3.0)

Como os clientes acessam o portal pela rede, a AGPL exige que o código-fonte modificado esteja
disponível para eles. Mantenha este repositório **público** e, se quiser, inclua um link para ele no
rodapé ou na tela "Sobre". Os avisos de copyright e os arquivos `LICENSE*` do Metabase devem permanecer.
"Metabase" é marca registrada da Metabase, Inc.; este fork não é afiliado nem endossado por ela.

## Filtragem por cliente (um painel para todos os clientes)

Um único painel "master" e um único conjunto de perguntas servem todos os clientes. O SQL das perguntas
usa **marcadores** no lugar dos códigos do cliente, e o servidor troca cada marcador antes de rodar a consulta
(`src/metabase/query_processor/middleware/all_client_scope.clj`, logo antes de `substitute-parameters`).

| Marcador | Código (Admin → Pessoas → Grupos → grupo de cliente) | Exemplo |
|---|---|---|
| `__ALL_ERP__` | Códigos dos clientes no ERP AML | `6,7,23` |
| `__ALL_TACTICAL__` | Nome do cliente no Tactical RMM | `Tecmar` |
| `__ALL_ZABBIX__` | Nome do grupo de hosts no Zabbix, como aparece na interface (vários: separados por vírgula) | `Tecmar` |
| `__ALL_BACULA__` | ClientId do Bacula (vários: separados por vírgula) | `6` |
| `__ALL_WAZUH__` | Schema da auditoria (serviço **auditoria**) | `cli_tecmar` |
| `__ALL_SQUID__` | Cliente nos logs de navegação (serviço **navegacao**) | `tecmar` |

Exemplo: `WHERE A.CLIENTE_ATD IN (__ALL_ERP__) /* {{all_cliente}} */`

Quem vê o quê:
- **Usuário de grupo de cliente:** sempre os códigos do próprio grupo; o filtro "Cliente" fica escondido e
  qualquer valor enviado é ignorado. Abas de serviço não contratado (nome com "Auditoria" ou "Navega")
  mostram uma prévia desfocada com dados fictícios e os botões de WhatsApp e e-mail comercial; o servidor
  recusa as consultas desses serviços.
- **Equipe da ALL:** escolhe o cliente no filtro de painel com slug `cliente`, ligado à variável
  `{{all_cliente}}` de cada pergunta (pelo nome do grupo). Vê todos os serviços, contratados ou não.
- **Sem login** (link público, embed): consultas com marcadores falham. Não use compartilhamento público
  nesses painéis.

Regras de segurança: valores só com letras, números, espaço e `. , : _ - /` (sem `--`); marcador sem código configurado
faz a consulta falhar; o cache é calculado depois da troca, então resultados de clientes não se misturam.
Assinaturas de painel rodam com o usuário que as criou: a equipe deve escolher o cliente no filtro da assinatura.

Contatos do convite e textos dos serviços: `frontend/src/metabase/branding/client-services.ts`.
Testes: `test/metabase/query_processor/middleware/all_client_scope_test.clj` (workflow `all-test.yml`).
Imagem de teste: push no branch `all-filtro-cliente` gera `ghcr.io/<usuário>/portal-bi:teste`.

### Criar o painel modelo a partir do painel da Tecmar

`bin/all-painel-modelo.py` (Python 3, sem dependências) copia o painel 19 para a pasta "Modelo (teste)",
trocando os códigos da Tecmar pelos marcadores, recria abas, posições e o filtro "Cliente", e com
`--configurar-grupo` cria o grupo "Grupo Tecmar" já marcado como cliente e com os códigos preenchidos.

```bash
export MB_URL=http://localhost:3001 MB_KEY=mb_...        # Metabase de destino
python3 bin/all-painel-modelo.py                          # só mostra o plano
python3 bin/all-painel-modelo.py --aplicar --configurar-grupo
```

### Filtro "Cliente" da equipe
O filtro de painel com slug `cliente` (lista estática) lista sozinho todos os grupos marcados como cliente,
em ordem alfabética (`metabase.parameters.custom-values`). Usuários de cliente não recebem a lista e não veem o filtro.

### Filtros por aba (Período, Dispositivo, Empresa)
`bin/all-filtros-abas.py` acrescenta às perguntas do painel modelo as variáveis `{{periodo}}` (opções fáceis:
7/30/90 dias, 12 meses, este mês, mês passado, este ano, tudo), `{{dispositivo}}` (texto, "contém") e
`{{empresa}}` (lista das empresas do cliente no ERP). Cada aba tem seu filtro de Período com padrão próprio.
O filtro Empresa (slug `empresa`) fica escondido para clientes cujo código ERP tem uma empresa só
(`all_client_multi_company` no usuário).

A versão atual é `bin/all-filtros-abas-v2.py`: todos os filtros são dropdown (perguntas "Lista · ..." com os
marcadores `__ALL_*__`, então cada cliente só vê os próprios valores) ou calendário (Data inicial / Data final).
As listas da equipe seguem o cliente escolhido no filtro Cliente (filtros ligados). `bin/all-testa-filtros.py`
roda todas as perguntas sem filtro, com datas e com o primeiro valor de cada lista.

### Publicar o painel do teste na produção
O painel é montado e testado no Metabase_Teste e depois publicado com `bin/all-publicar-painel.py`. O script
copia o painel, as perguntas e as listas, trocando os ids. Rodando de novo, atualiza no lugar (perguntas e abas
casadas pelo nome), então os links continuam valendo. `--grupos` copia também os códigos e serviços dos grupos
de cliente. Sem `--aplicar` só mostra o que faria.

```bash
MB_SRC_URL=http://localhost:3002 MB_SRC_KEY=<chave do teste> \
MB_URL=http://localhost:3000 MB_KEY=<chave da produção> \
python3 all-publicar-painel.py --grupos            # confira e repita com --aplicar
```
