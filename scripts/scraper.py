"""
Top Estética Bucal — Scraper PIX Doutores v3
Corrigido para o sistema real: campo Método é multiselect com tags,
datas são inputs normais com formato dd/mm/yyyy
"""
import asyncio
import json
import os
import datetime
import re
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

USUARIO = os.environ.get("SISTEMA_USER", "MANUS")
SENHA   = os.environ.get("SISTEMA_PASS", "MANUS2026")

CIDADES = [
    {"nome": "CAXIAS",       "url": "http://caxias.topesteticabucal.com.br/sistema"},
    {"nome": "FARROUPILHA",  "url": "http://farroupilha.topesteticabucal.com.br/sistema"},
    {"nome": "SOLEDADE",     "url": "http://soledade.topesteticabucal.com.br/sistema"},
    {"nome": "ENCANTADO",    "url": "https://encantado.topesteticabucal.com.br/sistema"},
    {"nome": "GARIBALDI",    "url": "http://garibaldi.topesteticabucal.com.br/sistema"},
    {"nome": "VERANÓPOLIS",  "url": "http://veranopolis.topesteticabucal.com.br/sistema"},
    {"nome": "SS DO CAÍ",    "url": "https://ssdocai.topesteticabucal.com.br/sistema"},
    {"nome": "BENTO",        "url": "http://bento.topesteticabucal.com.br/sistema"},
    {"nome": "FLORES",       "url": "https://flores.topesteticabucal.com.br/sistema"},
]

def get_periodo():
    hoje = datetime.date.today()
    primeiro = f"01/{hoje.month:02d}/{hoje.year}"
    if hoje.month == 12:
        ultimo_dia = 31
    else:
        ultimo_dia = (datetime.date(hoje.year, hoje.month + 1, 1) - datetime.timedelta(days=1)).day
    ultimo = f"{ultimo_dia}/{hoje.month:02d}/{hoje.year}"
    return primeiro, ultimo, f"{hoje.month:02d}/{hoje.year}"

def parse_valor(texto):
    if not texto:
        return 0.0
    limpo = re.sub(r'[^\d,\.\-]', '', str(texto))
    if ',' in limpo and '.' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    elif ',' in limpo:
        limpo = limpo.replace(',', '.')
    try:
        return abs(float(limpo))
    except:
        return 0.0

async def scrape_cidade(browser, cidade, primeiro_dia, ultimo_dia):
    print(f"\n→ {cidade['nome']}: conectando...")
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    dados = []

    try:
        # ── 1. LOGIN ─────────────────────────────────────────────────────────
        await page.goto(cidade["url"], timeout=25000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        await page.fill('input[name="usuario"]', USUARIO)
        await page.fill('input[name="senha"]', SENHA)
        await page.click('input[type="submit"]')
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        print(f"  ✓ Login OK — URL: {page.url}")

        # ── 2. ACESSAR DEMONSTRATIVO DIRETO PELA URL ─────────────────────────
        base = cidade["url"].rstrip("/")
        demo_url = f"{base}/financeiro/demonstrativo"
        await page.goto(demo_url, timeout=20000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        print(f"  ✓ Demonstrativo: {page.url}")

        # ── 3. SELECIONAR "PIX DOUTORES" NO CAMPO MÉTODO ─────────────────────
        # O campo Método é um multiselect com tags (chosen/select2/custom)
        # Estratégia: clicar no campo, digitar "Pix", clicar na opção
        print(f"  → Selecionando Pix Doutores...")

        try:
            # Tenta via JavaScript — encontra o select hidden por trás do componente
            # e dispara o evento de seleção
            resultado = await page.evaluate("""
                () => {
                    // Procura select com option "Pix Doutores"
                    const selects = document.querySelectorAll('select');
                    for (const sel of selects) {
                        for (const opt of sel.options) {
                            if (opt.text.toLowerCase().includes('pix') && 
                                opt.text.toLowerCase().includes('doutor')) {
                                // Seleciona o valor
                                sel.value = opt.value;
                                // Dispara eventos para o componente detectar
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                                sel.dispatchEvent(new Event('input', {bubbles: true}));
                                return {ok: true, texto: opt.text, valor: opt.value, seletorNome: sel.name || sel.id};
                            }
                        }
                    }
                    return {ok: false, motivo: 'option nao encontrada'};
                }
            """)
            print(f"  → Select JS: {resultado}")
        except Exception as e:
            print(f"  → Erro JS select: {e}")

        await page.wait_for_timeout(1000)

        # Tenta também via chosen/select2: clicar no input do componente e selecionar
        try:
            # Clicar no campo "Método" (div/input do chosen)
            await page.click('text=Selecione um método', timeout=2000)
            await page.wait_for_timeout(500)
            # Digitar para filtrar
            await page.keyboard.type('Pix Doutores')
            await page.wait_for_timeout(800)
            # Clicar na opção que aparecer
            await page.click('.chosen-results li:has-text("Pix Doutores")', timeout=2000)
            print(f"  ✓ Chosen: Pix Doutores selecionado")
        except:
            pass

        try:
            # Tenta select2
            await page.click('.select2-search__field', timeout=1000)
            await page.keyboard.type('Pix Doutores')
            await page.wait_for_timeout(500)
            await page.click('.select2-results__option:has-text("Pix Doutores")', timeout=1000)
            print(f"  ✓ Select2: Pix Doutores selecionado")
        except:
            pass

        # ── 4. PREENCHER DATAS ───────────────────────────────────────────────
        print(f"  → Preenchendo período: {primeiro_dia} a {ultimo_dia}...")

        # As datas aparecem como inputs de texto com formato dd/mm/yyyy
        # Vamos usar JavaScript para preencher diretamente
        datas_ok = await page.evaluate(f"""
            () => {{
                const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                let ini_ok = false, fim_ok = false;
                inputs.forEach(inp => {{
                    const nome = (inp.name || inp.id || inp.placeholder || '').toLowerCase();
                    // Campo data início
                    if (!ini_ok && (nome.includes('ini') || nome.includes('inicio') || nome.includes('de') || nome.includes('from'))) {{
                        inp.value = '{primeiro_dia}';
                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                        inp.dispatchEvent(new Event('blur', {{bubbles: true}}));
                        ini_ok = true;
                    }}
                    // Campo data fim
                    if (!fim_ok && (nome.includes('fim') || nome.includes('final') || nome.includes('ate') || nome.includes('to') || nome.includes('até'))) {{
                        inp.value = '{ultimo_dia}';
                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                        inp.dispatchEvent(new Event('blur', {{bubbles: true}}));
                        fim_ok = true;
                    }}
                }});
                
                // Se não achou pelos nomes, pega os dois primeiros inputs de texto que pareçam datas
                if (!ini_ok || !fim_ok) {{
                    const dateInputs = [...inputs].filter(inp => {{
                        const val = inp.value || '';
                        const ph = inp.placeholder || '';
                        return ph.includes('/') || ph.includes('data') || ph.includes('Data') || val.match(/\\d{{2}}\\/\\d{{2}}\\/\\d{{4}}/);
                    }});
                    if (dateInputs[0] && !ini_ok) {{
                        dateInputs[0].value = '{primeiro_dia}';
                        dateInputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                        ini_ok = true;
                    }}
                    if (dateInputs[1] && !fim_ok) {{
                        dateInputs[1].value = '{ultimo_dia}';
                        dateInputs[1].dispatchEvent(new Event('change', {{bubbles: true}}));
                        fim_ok = true;
                    }}
                }}
                return {{ini_ok, fim_ok}};
            }}
        """)
        print(f"  → Datas: {datas_ok}")

        # Fallback: tentar pelos seletores mais comuns
        if not datas_ok.get('ini_ok'):
            for sel in ['input[name="data_ini"]', 'input[name="dt_ini"]', '#data_ini', '#dt_ini',
                        'input[name="inicio"]', 'input[name="de"]']:
                try:
                    await page.fill(sel, primeiro_dia, timeout=1500)
                    print(f"  ✓ Data início via seletor: {sel}")
                    break
                except:
                    continue

        if not datas_ok.get('fim_ok'):
            for sel in ['input[name="data_fim"]', 'input[name="dt_fim"]', '#data_fim', '#dt_fim',
                        'input[name="fim"]', 'input[name="ate"]']:
                try:
                    await page.fill(sel, ultimo_dia, timeout=1500)
                    print(f"  ✓ Data fim via seletor: {sel}")
                    break
                except:
                    continue

        await page.wait_for_timeout(500)

        # ── 5. CLICAR EM BUSCAR ──────────────────────────────────────────────
        print(f"  → Clicando em Buscar...")
        for sel in ['input[value="Buscar"]', 'button:has-text("Buscar")', 
                    'input[type="submit"]', 'button[type="submit"]']:
            try:
                await page.click(sel, timeout=3000)
                print(f"  ✓ Buscar clicado: {sel}")
                break
            except:
                continue

        await page.wait_for_load_state("networkidle", timeout=20000)
        await page.wait_for_timeout(3000)

        # ── 6. EXTRAIR DADOS ─────────────────────────────────────────────────
        print(f"  → Extraindo dados da tabela...")

        # Captura estrutura completa da tabela para debug
        estrutura = await page.evaluate("""
            () => {
                const tabelas = [];
                document.querySelectorAll('table').forEach((tbl, ti) => {
                    const linhas = [];
                    tbl.querySelectorAll('tr').forEach((tr, ri) => {
                        const cells = [...tr.querySelectorAll('td, th')].map(c => c.innerText.trim().slice(0, 60));
                        if (cells.some(c => c)) linhas.push(cells);
                    });
                    tabelas.push({tabela: ti, linhas: linhas.slice(0, 20)});
                });
                return tabelas;
            }
        """)
        
        print(f"  → Tabelas encontradas: {len(estrutura)}")
        for tbl in estrutura:
            print(f"     Tabela {tbl['tabela']}:")
            for linha in tbl['linhas'][:10]:
                print(f"       {linha}")

        # Extrair linhas de dados
        linhas_dados = await page.evaluate("""
            () => {
                const resultado = [];
                document.querySelectorAll('table tr').forEach(tr => {
                    const cells = [...tr.querySelectorAll('td')].map(c => c.innerText.trim());
                    if (cells.length < 4) return;
                    // Linha com data no formato dd/mm/yyyy
                    if (!/^\d{2}\/\d{2}\/\d{4}/.test(cells[0])) return;
                    resultado.push({
                        data:      cells[0] || '',
                        metodo:    cells[1] || '',
                        origem:    cells[2] || '',
                        valor:     cells[3] || '0',
                        valor_desc:cells[4] || '',
                        vezes:     cells[5] || '',
                        nsu:       cells[6] || '',
                        nf:        cells[7] || '',
                        saldo:     cells[8] || '',
                    });
                });
                return resultado;
            }
        """)

        print(f"  ✓ {len(linhas_dados)} linhas com data encontradas")
        
        # Filtrar Pix Doutores (ou pegar tudo se não filtrou pelo método)
        for row in linhas_dados:
            metodo = row.get('metodo', '').lower()
            if 'pix' in metodo and 'doutor' in metodo:
                dados.append(row)
            elif not linhas_dados or len([r for r in linhas_dados if 'pix' in r.get('metodo','').lower() and 'doutor' in r.get('metodo','').lower()]) == 0:
                # Se nenhum Pix Doutores foi encontrado, pega todos e filtra depois pelo NF
                if row.get('nf'):
                    dados.append(row)

        print(f"  ✓ {len(dados)} lançamentos Pix Doutores")

    except Exception as e:
        print(f"  ✗ ERRO em {cidade['nome']}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await page.close()
        await context.close()

    # Processar
    resultado = []
    for row in dados:
        origem = row.get("origem", "")
        m = re.match(r"Recebido de (.+?)(?:\s+Pago por:|$)", origem, re.IGNORECASE)
        paciente = m.group(1).strip() if m else origem
        m2 = re.search(r"Pago por:\s*(.+)", origem, re.IGNORECASE)
        responsavel = m2.group(1).strip() if m2 else ""
        resultado.append({
            "data":        row["data"],
            "cidade":      cidade["nome"],
            "paciente":    paciente,
            "responsavel": responsavel,
            "valor":       parse_valor(row["valor"]),
            "nf":          row["nf"],
            "metodo":      row.get("metodo", ""),
        })
    return resultado


async def main():
    primeiro, ultimo, mes_ref = get_periodo()
    print(f"=== Top Estética Bucal — Scraper v3 ===")
    print(f"Período: {primeiro} → {ultimo} | Mês: {mes_ref}")

    todos = []
    erros = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        for cidade in CIDADES:
            try:
                registros = await scrape_cidade(browser, cidade, primeiro, ultimo)
                todos.extend(registros)
                print(f"  ✓ {cidade['nome']}: {len(registros)} registros")
            except Exception as e:
                erros.append({"cidade": cidade["nome"], "erro": str(e)})
                print(f"  ✗ {cidade['nome']}: {e}")
        await browser.close()

    output = {
        "gerado_em":  datetime.datetime.now().isoformat(),
        "mes_ref":    mes_ref,
        "total_regs": len(todos),
        "cidades_ok": len(CIDADES) - len(erros),
        "erros":      erros,
        "dados":      todos
    }

    with open("dados.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== Concluído: {len(todos)} registros | {len(erros)} erros ===")

if __name__ == "__main__":
    asyncio.run(main())
