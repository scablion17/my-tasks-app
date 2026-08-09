from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
import socket

app = FastAPI(title="Local Tasks API")

# Veritabanı Kurulumu
def init_db():
    conn = sqlite3.connect("hatirlatıcılar.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hatirlaticilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            icerik TEXT,
            hedef_tarih TEXT NOT NULL,
            erken_hatirlatma_dk INTEGER DEFAULT 0,
            hatirlatma_zamani TEXT NOT NULL,
            tamamlandi INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class HatirlaticiCreate(BaseModel):
    baslik: str
    icerik: str = ""
    hedef_tarih: str  # YYYY-MM-DD HH:MM
    erken_hatirlatma_dk: int = 0

@app.post("/ekle")
def hatirlatici_ekle(item: HatirlaticiCreate):
    try:
        hedef_dt = datetime.strptime(item.hedef_tarih, "%Y-%m-%d %H:%M")
        hatirlatma_dt = hedef_dt - timedelta(minutes=item.erken_hatirlatma_dk)
        
        conn = sqlite3.connect("hatirlatıcılar.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO hatirlaticilar (baslik, icerik, hedef_tarih, erken_hatirlatma_dk, hatirlatma_zamani)
            VALUES (?, ?, ?, ?, ?)
        ''', (item.baslik, item.icerik, item.hedef_tarih, item.erken_hatirlatma_dk, hatirlatma_dt.strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        return {"durum": "Basarili"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/tum-gorevler")
def tum_gorevleri_getir():
    conn = sqlite3.connect("hatirlatıcılar.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, baslik, icerik, hedef_tarih, erken_hatirlatma_dk, tamamlandi 
        FROM hatirlaticilar 
        ORDER BY tamamlandi ASC, hedef_tarih ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    gorevler = []
    for r in rows:
        gorevler.append({
            "id": r[0], "baslik": r[1], "icerik": r[2], 
            "hedef_tarih": r[3], "erken_hatirlatma_dk": r[4], "tamamlandi": bool(r[5])
        })
    return gorevler

@app.post("/tamamla/{gorev_id}")
def gorev_durum_degistir(gorev_id: int):
    conn = sqlite3.connect("hatirlatıcılar.db")
    cursor = conn.cursor()
    cursor.execute('UPDATE hatirlaticilar SET tamamlandi = CASE WHEN tamamlandi = 0 THEN 1 ELSE 0 END WHERE id = ?', (gorev_id,))
    conn.commit()
    conn.close()
    return {"durum": "Basarili"}

@app.delete("/sil/{gorev_id}")
def gorev_sil(gorev_id: int):
    conn = sqlite3.connect("hatirlatıcılar.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM hatirlaticilar WHERE id = ?', (gorev_id,))
    conn.commit()
    conn.close()
    return {"durum": "Basarili"}

@app.get("/aktif-hatirlatmalar")
def aktif_hatirlatmalari_getir():
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect("hatirlatıcılar.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, baslik, icerik, hedef_tarih FROM hatirlaticilar 
        WHERE hatirlatma_zamani <= ? AND tamamlandi = 0
    ''', (simdi,))
    rows = cursor.fetchall()
    hatirlaticilar = [{"id": r[0], "baslik": r[1], "icerik": r[2], "hedef_tarih": r[3]} for r in rows]
    conn.close()
    return hatirlaticilar

# Modern Frontend Arayüzü (Microsoft To-Do & Google Tasks Mimarisi)
@app.get("/", response_class=HTMLResponse)
def ui():
    return """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Local Tasks</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        </style>
    </head>
    <body class="bg-slate-100 text-slate-800 min-h-screen flex justify-center py-6 px-4">
        <div class="w-full max-w-xl bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden border border-slate-200 h-[85vh]">
            
            <!-- Header -->
            <div class="bg-indigo-600 text-white p-5 flex justify-between items-center shadow-md">
                <div class="flex items-center space-x-3">
                    <i class="fa-solid fa-check-double text-2xl"></i>
                    <h1 class="text-xl font-bold tracking-wide">Görevlerim</h1>
                </div>
                <span id="gorev-sayisi" class="bg-indigo-700 text-indigo-100 text-xs px-3 py-1 rounded-full font-medium">0 Görev</span>
            </div>

            <!-- Task Input Form -->
            <form id="task-form" class="p-4 border-b border-slate-100 bg-slate-50 space-y-3">
                <div class="relative">
                    <input type="text" id="baslik" placeholder="Yeni bir görev ekle..." required 
                           class="w-full pl-4 pr-10 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm text-sm">
                </div>
                
                <div class="grid grid-cols-2 gap-2 text-xs">
                    <div>
                        <label class="block text-slate-500 mb-1 font-medium">Tarih & Saat</label>
                        <input type="datetime-local" id="hedef_tarih" required 
                               class="w-full p-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700">
                    </div>
                    <div>
                        <label class="block text-slate-500 mb-1 font-medium">Erken Hatırlatma</label>
                        <select id="erken_hatirlatma_dk" class="w-full p-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700">
                            <option value="0">Tam Zamanında</option>
                            <option value="5">5 Dakika Önce</option>
                            <option value="15">15 Dakika Önce</option>
                            <option value="60">1 Saat Önce</option>
                            <option value="1440">1 Gün Önce</option>
                            <option value="10080">1 Haftalık Önce</option>
                        </select>
                    </div>
                </div>

                <textarea id="icerik" placeholder="Not ekle (isteğe bağlı)..." rows="2" 
                          class="w-full p-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-700"></textarea>

                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 rounded-xl transition duration-200 shadow-sm text-sm flex items-center justify-center space-x-2">
                    <i class="fa-solid fa-plus"></i>
                    <span>Ekle</span>
                </button>
            </form>

            <!-- Task List -->
            <div id="task-list" class="flex-1 overflow-y-auto p-4 space-y-2">
                <!-- Görevler JS ile buraya yüklenecek -->
            </div>
        </div>

        <script>
            // Varsayılan tarihi şu anki zamana kur
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            document.getElementById('hedef_tarih').value = now.toISOString().slice(0,16);

            async function gorevleriGetir() {
                const res = await fetch('/tum-gorevler');
                const data = await res.json();
                const container = document.getElementById('task-list');
                const countBadge = document.getElementById('gorev-sayisi');
                
                container.innerHTML = '';
                countBadge.innerText = `${data.filter(g => !g.tamamlandi).length} Görev`;

                if(data.length === 0) {
                    container.innerHTML = `
                        <div class="text-center py-12 text-slate-400 space-y-2">
                            <i class="fa-regular fa-clipboard text-4xl"></i>
                            <p class="text-sm">Henüz bir görev eklenmemiş.</p>
                        </div>`;
                    return;
                }

                data.forEach(g => {
                    const el = document.createElement('div');
                    el.className = `p-3.5 rounded-xl border transition duration-150 flex items-start justify-between space-x-3 ${g.tamamlandi ? 'bg-slate-50 border-slate-200 opacity-60' : 'bg-white border-slate-200 shadow-sm hover:border-indigo-200'}`;
                    
                    el.innerHTML = `
                        <div class="flex items-start space-x-3 flex-1 min-w-0">
                            <button onclick="tamamla(${g.id})" class="mt-0.5 text-lg ${g.tamamlandi ? 'text-indigo-600' : 'text-slate-300 hover:text-indigo-500'}">
                                <i class="${g.tamamlandi ? 'fa-solid fa-circle-check' : 'fa-regular fa-circle'}"></i>
                            </button>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm font-medium ${g.tamamlandi ? 'line-through text-slate-400' : 'text-slate-800'} truncate">${g.baslik}</p>
                                ${g.icerik ? `<p class="text-xs text-slate-500 mt-0.5 truncate">${g.icerik}</p>` : ''}
                                <div class="flex items-center space-x-3 mt-1.5 text-[11px] text-slate-400">
                                    <span><i class="fa-regular fa-clock mr-1"></i>${g.hedef_tarih}</span>
                                    ${g.erken_hatirlatma_dk > 0 ? `<span><i class="fa-regular fa-bell mr-1"></i>${g.erken_hatirlatma_dk}dk önce</span>` : ''}
                                </div>
                            </div>
                        </div>
                        <button onclick="sil(${g.id})" class="text-slate-300 hover:text-red-500 text-sm p-1">
                            <i class="fa-regular fa-trash-can"></i>
                        </button>
                    `;
                    container.appendChild(el);
                });
            }

            document.getElementById('task-form').onsubmit = async (e) => {
                e.preventDefault();
                const baslik = document.getElementById('baslik').value;
                const icerik = document.getElementById('icerik').value;
                const rawDate = document.getElementById('hedef_tarih').value; // YYYY-MM-DDTHH:MM
                const formattedDate = rawDate.replace('T', ' ');
                const erken_hatirlatma_dk = parseInt(document.getElementById('erken_hatirlatma_dk').value);

                await fetch('/ekle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        baslik, icerik, hedef_tarih: formattedDate, erken_hatirlatma_dk
                    })
                });

                document.getElementById('baslik').value = '';
                document.getElementById('icerik').value = '';
                gorevleriGetir();
            };

            async function tamamla(id) {
                await fetch(`/tamamla/${id}`, {method: 'POST'});
                gorevleriGetir();
            }

            async function sil(id) {
                await fetch(`/sil/${id}`, {method: 'DELETE'});
                gorevleriGetir();
            }

            gorevleriGetir();
        </script>
    </body>
    </html>
    """

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# YENİ KOD (Render Bulut Sunucusu + Lokal Uyumlu)
import os

if __name__ == "__main__":
    import uvicorn
    # Render'ın atadığı portu oku, eğer yoksa (lokaldeysek) varsayılan 8000'i kullan
    port = int(os.environ.get("PORT", 8000))
    print(f"\n--- Uygulama Başlatılıyor (Port: {port}) ---")
    uvicorn.run(app, host="0.0.0.0", port=port)
