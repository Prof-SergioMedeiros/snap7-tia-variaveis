#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snap7_gui.py - Interface grafica (Tkinter) para o projeto TIA Portal V21
"Snap7_Variaveis".

  ENTRADAS  = DB_Snap7 (DB1)       -> o Python escreve / le
  SAIDAS    = DB_Snap7_Resp (DB2)  -> calculadas pela FC_Logica_Snap7 no PLC (somente leitura)

Logica no PLC (FC_Logica_Snap7, chamada no OB1):
  E_Bool01        = Bool_0 AND Bool_1
  OU_Bool23       = Bool_2 OR Bool_3
  NAO_Bool4       = NOT Bool_4
  Qualquer_Bool   = algum Bool_0..7 ligado
  Soma_Bits       = quantidade de Bool_0..7 ligados
  Int_Mais1       = Int_Val + 1
  DInt_Dobro      = Int_Val * 2
  Real_Fahrenheit = Real_Val * 1.8 + 32
  LReal_Raiz      = raiz quadrada de |LReal_Val|
  String_Eco      = 'Eco: ' + String_Val
  Len_String      = tamanho de String_Val
  Word_Invertida  = NOT Word_Val
  Contador        = +1 a cada 100 ms   (Bool_6 pausa, Bool_7 zera)
  Heartbeat       = alterna a cada 500 ms

Uso:  python snap7_gui.py
"""

import struct
import tkinter as tk
from tkinter import ttk

from snap7.client import Client

# --------------------------------------------------------------------------
# Configuracao
# --------------------------------------------------------------------------
IP = "192.168.0.1"
RACK = 0
SLOT = 1
DB_IN, SIZE_IN = 1, 52      # DB_Snap7
DB_OUT, SIZE_OUT = 2, 60    # DB_Snap7_Resp (somente os 60 primeiros bytes)
POLL_MS = 300

# nome: (tipo, offset, extra)   extra = bit (Bool) ou tamanho maximo (String)
ENTRADAS = {
    "Bool_0": ("bool", 0, 0), "Bool_1": ("bool", 0, 1),
    "Bool_2": ("bool", 0, 2), "Bool_3": ("bool", 0, 3),
    "Bool_4": ("bool", 0, 4), "Bool_5": ("bool", 0, 5),
    "Bool_6": ("bool", 0, 6), "Bool_7": ("bool", 0, 7),
    "Byte_Val": ("byte", 1, 0),
    "Int_Val": ("int", 2, 0),
    "UInt_Val": ("uint", 4, 0),
    "Word_Val": ("word", 6, 0),
    "LReal_Val": ("lreal", 8, 0),
    "DInt_Val": ("dint", 16, 0),
    "UDInt_Val": ("udint", 20, 0),
    "Real_Val": ("real", 24, 0),
    "String_Val": ("string", 28, 20),
    "SInt_Val": ("sint", 50, 0),
    "USInt_Val": ("usint", 51, 0),
}

SAIDAS = {
    "Heartbeat": ("bool", 0, 0),
    "E_Bool01": ("bool", 0, 1),
    "OU_Bool23": ("bool", 0, 2),
    "NAO_Bool4": ("bool", 0, 3),
    "Qualquer_Bool": ("bool", 0, 4),
    "Soma_Bits": ("byte", 1, 0),
    "Int_Mais1": ("int", 2, 0),
    "DInt_Dobro": ("dint", 4, 0),
    "Contador": ("dint", 8, 0),
    "Real_Fahrenheit": ("real", 12, 0),
    "LReal_Raiz": ("lreal", 16, 0),
    "String_Eco": ("string", 24, 30),
    "Len_String": ("int", 56, 0),
    "Word_Invertida": ("word", 58, 0),
}

FORMATOS = {
    "byte": ">B", "int": ">h", "uint": ">H", "word": ">H", "lreal": ">d",
    "dint": ">i", "udint": ">I", "real": ">f", "sint": ">b", "usint": ">B",
}

FAIXAS = {
    "byte": "0..255 ou 0xFF", "int": "-32768..32767", "uint": "0..65535",
    "word": "0..65535 ou 0xFFFF", "lreal": "decimal", "dint": "-2147483648..2147483647",
    "udint": "0..4294967295", "real": "decimal", "string": "ate 20 caracteres",
    "sint": "-128..127", "usint": "0..255",
}

DICAS = {"Bool_6": "pausa o contador", "Bool_7": "zera o contador"}

COR_ON = "#2ecc71"
COR_OFF = "#b5b5b5"
FONTE_MONO = ("Consolas", 10)


# --------------------------------------------------------------------------
# Codificacao / decodificacao (S7 = big-endian)
# --------------------------------------------------------------------------
def decodificar(tipo, extra, buf, base=0):
    if tipo == "bool":
        return bool((buf[base] >> extra) & 1)
    if tipo == "string":
        max_len = buf[base]
        atual = min(buf[base + 1], max_len, extra)
        return bytes(buf[base + 2: base + 2 + atual]).decode("latin-1")
    return struct.unpack_from(FORMATOS[tipo], buf, base)[0]


def converter_texto(tipo, texto):
    t = texto.strip()
    if tipo == "string":
        return texto
    if tipo in ("real", "lreal"):
        return float(t.replace(",", "."))
    return int(t, 0)  # aceita 123, 0xFF, 0b101


def escrever(cli, nome, valor):
    """Escreve uma variavel de ENTRADAS (DB1)."""
    tipo, off, extra = ENTRADAS[nome]
    if tipo == "bool":
        dado = bytearray(cli.db_read(DB_IN, off, 1))
        if valor:
            dado[0] |= 1 << extra
        else:
            dado[0] &= ~(1 << extra) & 0xFF
    elif tipo == "string":
        b = str(valor).encode("latin-1", errors="replace")[:extra]
        dado = bytearray([extra, len(b)]) + bytearray(b.ljust(extra, b"\x00"))
    else:
        try:
            dado = bytearray(struct.pack(FORMATOS[tipo], valor))
        except struct.error as e:
            raise ValueError(f"Valor fora da faixa de {tipo.upper()}: {valor}") from e
    cli.db_write(DB_IN, off, dado)


def fmt(valor):
    if isinstance(valor, float):
        return f"{valor:.6g}"
    return str(valor)


# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Snap7 - Variaveis TIA Portal V21")
        self.cli = None
        self.status = tk.StringVar(value="Desconectado")
        self.bool_in = {}   # nome -> BooleanVar
        self.val_in = {}    # nome -> StringVar (valor lido do PLC)
        self.entradas = {}  # nome -> Entry
        self.led = {}       # nome -> (canvas, item)
        self.val_out = {}   # nome -> StringVar

        self._montar_topo()
        self._montar_entradas()
        self._montar_saidas()
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 8))

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.after(POLL_MS, self.poll)

    # ---- montagem ---------------------------------------------------------
    def _montar_topo(self):
        f = ttk.Frame(self)
        f.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        self.ip = tk.StringVar(value=IP)
        self.rack = tk.StringVar(value=str(RACK))
        self.slot = tk.StringVar(value=str(SLOT))
        ttk.Label(f, text="IP:").pack(side="left")
        ttk.Entry(f, textvariable=self.ip, width=16).pack(side="left", padx=(2, 10))
        ttk.Label(f, text="Rack:").pack(side="left")
        ttk.Entry(f, textvariable=self.rack, width=4).pack(side="left", padx=(2, 10))
        ttk.Label(f, text="Slot:").pack(side="left")
        ttk.Entry(f, textvariable=self.slot, width=4).pack(side="left", padx=(2, 10))
        self.btn = ttk.Button(f, text="Conectar", command=self.alternar)
        self.btn.pack(side="left", padx=4)

    def _montar_entradas(self):
        f = ttk.LabelFrame(self, text="Entradas  (DB_Snap7 / DB1) - Python escreve e le")
        f.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        fb = ttk.LabelFrame(f, text="Bool")
        fb.grid(row=0, column=0, columnspan=5, sticky="ew", padx=4, pady=4)
        for i in range(8):
            nome = f"Bool_{i}"
            var = tk.BooleanVar(value=False)
            self.bool_in[nome] = var
            txt = nome + (f"  ({DICAS[nome]})" if nome in DICAS else "")
            ttk.Checkbutton(fb, text=txt, variable=var,
                            command=lambda n=nome: self.on_bool(n)).grid(
                row=i % 4, column=i // 4, sticky="w", padx=8, pady=1)

        for col, titulo in enumerate(("Variavel", "Tipo", "Valor no PLC", "Novo valor", "", "Faixa")):
            ttk.Label(f, text=titulo, font=("TkDefaultFont", 9, "bold")).grid(
                row=1, column=col, sticky="w", padx=4)

        linha = 2
        for nome, (tipo, off, extra) in ENTRADAS.items():
            if tipo == "bool":
                continue
            ttk.Label(f, text=nome).grid(row=linha, column=0, sticky="w", padx=4)
            ttk.Label(f, text=tipo.upper()).grid(row=linha, column=1, sticky="w", padx=4)
            sv = tk.StringVar(value="-")
            self.val_in[nome] = sv
            ttk.Label(f, textvariable=sv, font=FONTE_MONO, width=16).grid(
                row=linha, column=2, sticky="w", padx=4)
            e = ttk.Entry(f, width=16)
            e.grid(row=linha, column=3, padx=4, pady=1)
            e.bind("<Return>", lambda ev, n=nome: self.on_escrever(n))
            self.entradas[nome] = e
            ttk.Button(f, text="Escrever", command=lambda n=nome: self.on_escrever(n)).grid(
                row=linha, column=4, padx=4)
            ttk.Label(f, text=FAIXAS[tipo], foreground="#777777").grid(
                row=linha, column=5, sticky="w", padx=4)
            linha += 1

    def _montar_saidas(self):
        f = ttk.LabelFrame(self, text="Saidas  (DB_Snap7_Resp / DB2) - calculadas pelo PLC")
        f.grid(row=1, column=1, sticky="nsew", padx=8, pady=4)

        linha = 0
        for nome, (tipo, off, extra) in SAIDAS.items():
            if tipo == "bool":
                c = tk.Canvas(f, width=18, height=18, highlightthickness=0)
                item = c.create_oval(2, 2, 16, 16, fill=COR_OFF, outline="#666666")
                c.grid(row=linha, column=0, padx=4, pady=1)
                self.led[nome] = (c, item)
                ttk.Label(f, text=nome).grid(row=linha, column=1, sticky="w", padx=4)
                ttk.Label(f, text="BOOL").grid(row=linha, column=2, sticky="w", padx=4)
            else:
                ttk.Label(f, text="").grid(row=linha, column=0)
                ttk.Label(f, text=nome).grid(row=linha, column=1, sticky="w", padx=4)
                ttk.Label(f, text=tipo.upper()).grid(row=linha, column=2, sticky="w", padx=4)
                sv = tk.StringVar(value="-")
                self.val_out[nome] = sv
                ttk.Label(f, textvariable=sv, font=FONTE_MONO, width=20).grid(
                    row=linha, column=3, sticky="w", padx=4)
            linha += 1

    # ---- conexao ----------------------------------------------------------
    def alternar(self):
        if self.cli:
            self.desconectar("Desconectado")
            return
        ip = self.ip.get().strip()
        try:
            rack, slot = int(self.rack.get()), int(self.slot.get())
            cli = Client()
            cli.connect(ip, rack, slot)
        except Exception as e:
            self.status.set(f"Falha ao conectar em {ip}: {e}")
            return
        self.cli = cli
        self.btn.config(text="Desconectar")
        self.status.set(f"Conectado em {ip} (rack {rack}, slot {slot})")
        self.atualizar()

    def desconectar(self, msg):
        if self.cli:
            try:
                self.cli.disconnect()
            except Exception:
                pass
        self.cli = None
        self.btn.config(text="Conectar")
        self.status.set(msg)
        for sv in list(self.val_in.values()) + list(self.val_out.values()):
            sv.set("-")
        for c, item in self.led.values():
            c.itemconfig(item, fill=COR_OFF)

    def fechar(self):
        self.desconectar("Desconectado")
        self.destroy()

    # ---- leitura ----------------------------------------------------------
    def poll(self):
        self.atualizar()
        self.after(POLL_MS, self.poll)

    def atualizar(self):
        if not self.cli:
            return
        try:
            b1 = self.cli.db_read(DB_IN, 0, SIZE_IN)
        except Exception as e:
            self.desconectar(f"Falha de comunicacao: {e}")
            return
        try:
            b2 = self.cli.db_read(DB_OUT, 0, SIZE_OUT)
        except Exception:
            b2 = None

        for nome, (tipo, off, extra) in ENTRADAS.items():
            v = decodificar(tipo, extra, b1, off)
            if tipo == "bool":
                self.bool_in[nome].set(v)
            else:
                self.val_in[nome].set(fmt(v))

        for nome, (tipo, off, extra) in SAIDAS.items():
            if b2 is None:
                if tipo == "bool":
                    self.led[nome][0].itemconfig(self.led[nome][1], fill=COR_OFF)
                else:
                    self.val_out[nome].set("-")
                continue
            v = decodificar(tipo, extra, b2, off)
            if tipo == "bool":
                c, item = self.led[nome]
                c.itemconfig(item, fill=COR_ON if v else COR_OFF)
            else:
                self.val_out[nome].set(fmt(v))

        if b2 is None:
            self.status.set("Conectado - DB2 (DB_Snap7_Resp) indisponivel: baixe o projeto atualizado no PLC")

    # ---- escrita ----------------------------------------------------------
    def on_bool(self, nome):
        var = self.bool_in[nome]
        if not self.cli:
            var.set(not var.get())  # desfaz o clique
            self.status.set("Conecte-se ao PLC primeiro")
            return
        try:
            escrever(self.cli, nome, var.get())
            self.status.set(f"{nome} <- {var.get()}")
        except Exception as e:
            var.set(not var.get())
            self.desconectar(f"Falha de comunicacao: {e}")
            return
        self.atualizar()

    def on_escrever(self, nome):
        if not self.cli:
            self.status.set("Conecte-se ao PLC primeiro")
            return
        tipo = ENTRADAS[nome][0]
        try:
            valor = converter_texto(tipo, self.entradas[nome].get())
            escrever(self.cli, nome, valor)
        except ValueError as e:
            self.status.set(f"Valor invalido para {nome} ({tipo.upper()}): {e}")
            return
        except Exception as e:
            self.desconectar(f"Falha de comunicacao: {e}")
            return
        self.status.set(f"{nome} <- {fmt(valor)}")
        self.atualizar()


if __name__ == "__main__":
    App().mainloop()
