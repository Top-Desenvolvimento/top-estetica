"""
Top Estética Bucal — Scraper PIX Doutores
Roda via GitHub Actions a cada hora automaticamente.
Faz login em cada cidade, captura os dados de PIX Doutores e salva em dados.json
"""
import asyncio
import json
import os
import datetime
import re
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ── Credenciais (vêm das variáveis secretas do GitHub) ──────────────────────
USUARIO = os.environ.get("SISTEMA_USER", "MANUS")
SENHA   = os.environ.get("SISTEMA_PASS", "MANUS2026")

# ── Cidades ──────────────────────────────────────────────────────────────────
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

# ── Período: 1º ao último dia do mês atual ──────────────────────────────────
def get_periodo():
    hoje = datetime.date.today()
    primeiro = f"01/{hoje.month:02d}/{hoje.year}"
    ultimo_dia = (datetime.date(hoje.year, hoje.month % 12 + 1, 1) - datetime.timedelta(days=1)).day
    ultimo = f"{ultimo_dia}/{hoje.month:02d}/{hoje.year}"
    return primeiro, ultimo, f"{hoje.month:02d}/{hoje.year}"

def parse_valor(texto):
    """Converte '1.234,56 C' → 1234.56"""
    if not texto:
        return 0.0
    texto = re.sub(r'[^\d,\.\-]', '', texto.replace('.', '').replace(',', '.'))
    try:
        return float(texto)
    except:
        return 0.0

async def scrape_cidade(page, cidade, primeiro_dia, ultimo_dia):
    print(f"\n  → {cidade['nome']}: conectando...")
    dados = []
    try:
        # 1. Login
        await page.goto(cidade["url"], timeout=20000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        # Preencher usuário e senha
        user_sel = 'input[name="usuario"], input[name="user"], input[type="text"]:visible'
        pass_sel = 'input[name="senha"], input[name="password"], input[type="password"]:visible'

        await page.fill(user_sel, USUARIO)
        await page.fill(pass_sel, SENHA)

        # Submeter
        submit_sel = 'input[type="submit"], button[type="submit"], button:has-text("Entrar"), button:has-text("Login")'
        await page.click(submit_sel)
        await page.wait_for_load_state("networkidle", timeout=15000)

        print(f"     ✓ Login OK")

        # 2. Navegar para Finanças → Demonstrativo de Resultados
        # Tenta pelo menu
        try:
            await page.click('text=Finanças', timeout=5000)
            await page.wait_for_timeout(500)
            await page.click('text=Demonstrativo', timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            # Tenta URL direta
            base = cidade["url"].rstrip("/")
            await page.goto(f"{base}/financeiro/demonstrativo", timeout=15000, wait_until="domcontentloaded")

        await page.wait_for_timeout(1000)
        print(f"     ✓ Financeiro acessado")

        # 3. Selecionar método "Pix Doutores"
        try:
            metodo_sel = 'select[name="metodo"], select[name="metodo_pagamento"], select:has-option("Pix Doutores")'
            await page.select_option(metodo_sel, label="Pix Doutores", timeout=5000)
        except:
            try:
                await page.click('text=Pix Doutores', timeout=3000)
            except:
                print(f"     ⚠ Não encontrou seletor de método — tentando continuar")

        # 4. Preencher período
        try:
            await page.fill('input[name="data_ini"], #data_ini, input[placeholder*="nicio"]', primeiro_dia, timeout=3000)
            await page.fill('input[name="data_fim"], #data_fim, input[placeholder*="im"]',    ultimo_dia,   timeout=3000)
        except:
            print(f"     ⚠ Campos de data não encontrados")

        # 5. Buscar
        try:
            await page.click('button:has-text("Buscar"), input[value="Buscar"], button:has-text("Filtrar")', timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

        await page.wait_for_timeout(2000)
        print(f"     ✓ Filtro aplicado")

        # 6. Extrair dados da tabela
        dados = await page.evaluate("""
            () => {
                const rows = [];
                // Percorre todas as linhas de tabela
                document.querySelectorAll('table tr').forEach(tr => {
                    const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
                    if (cells.length < 4) return;

                    // Linha válida: coluna 0 = data (dd/mm/aaaa)
                    if (!/^\\d{2}\\/\\d{2}\\/\\d{4}/.test(cells[0])) return;

                    // Verificar se é Pix Doutores
                    const metPag = cells[1] || '';
                    if (!metPag.toLowerCase().includes('pix') || !metPag.toLowerCase().includes('doutor')) return;

                    rows.push({
                        data:        cells[0] || '',
                        metodo:      cells[1] || '',
                        origem:      cells[2] || '',
                        valor:       cells[3] || '0',
                        valor_desc:  cells[4] || cells[3] || '0',
                        vezes:       cells[5] || '1',
                        nsu:         cells[6] || '',
                        nf:          cells[7] || '',
                        saldo:       cells[8] || '',
                    });
                });
                return rows;
            }
        """)

        print(f"     ✓ {len(dados)} lançamentos encontrados")

    except PWTimeout as e:
        print(f"     ✗ TIMEOUT em {cidade['nome']}: {e}")
    except Exception as e:
        print(f"     ✗ ERRO em {cidade['nome']}: {e}")

    # Processar e enriquecer
    resultado = []
    for row in dados:
        origem = row.get("origem", "")
        # Extrair paciente
        m = re.match(r"Recebido de (.+?)(?:\s+Pago por:|$)", origem, re.IGNORECASE)
        paciente = m.group(1).strip() if m else origem

        # Extrair responsável
        m2 = re.search(r"Pago por:\s*(.+)", origem, re.IGNORECASE)
        responsavel = m2.group(1).strip() if m2 else ""

        resultado.append({
            "data":        row["data"],
            "cidade":      cidade["nome"],
            "paciente":    paciente,
            "responsavel": responsavel,
            "valor":       parse_valor(row["valor"]),
            "nf":          row["nf"],
            "origem_raw":  origem,
        })

    return resultado


async def main():
    primeiro, ultimo, mes_ref = get_periodo()
    print(f"=== Top Estética Bucal — Scraper PIX Doutores ===")
    print(f"Período: {primeiro} a {ultimo}")
    print(f"Cidades: {len(CIDADES)}\n")

    todos = []
    erros = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )

        for cidade in CIDADES:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()

            try:
                registros = await scrape_cidade(page, cidade, primeiro, ultimo)
                todos.extend(registros)
            except Exception as e:
                erros.append({"cidade": cidade["nome"], "erro": str(e)})
                print(f"  ✗ Falha geral em {cidade['nome']}: {e}")
            finally:
                await page.close()
                await context.close()

        await browser.close()

    # Salvar resultado
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

    print(f"\n=== Concluído ===")
    print(f"Total de registros: {len(todos)}")
    print(f"Cidades com erro:   {len(erros)}")
    if erros:
        for e in erros:
            print(f"  - {e['cidade']}: {e['erro']}")
    print(f"Arquivo salvo: dados.json")


if __name__ == "__main__":
    asyncio.run(main())
