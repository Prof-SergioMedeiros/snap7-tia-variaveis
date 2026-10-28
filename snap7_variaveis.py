#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snap7_variaveis.py - Leitura e escrita de variaveis (Bool, Int, Real, String...)
do projeto TIA Portal V21 "Snap7_Variaveis" via Snap7.

Requisitos no TIA / CPU:
  * DB_Snap7 (DB1) com acesso padrao (NAO otimizado)  -> ja configurado no projeto
  * PUT/GET habilitado na CPU                          -> ja configurado no projeto
  * Projeto baixado (hardware + software) no PLC / PLCSIM Advanced

Layout do DB1 (offsets absolutos, big-endian como o S7):
  0.0 .. 0.7  Bool_0 .. Bool_7
  1           Byte_Val      (Byte)
  2           Int_Val       (Int)
  4           UInt_Val      (UInt)
  6           Word_Val      (Word)
  8           LReal_Val     (LReal, 8 bytes)
  16          DInt_Val      (DInt)
  20          UDInt_Val     (UDInt)
  24          Real_Val      (Real)
  28          String_Val    (String[20], 22 bytes)
  50          SInt_Val      (SInt)
  51          USInt_Val     (USInt)
  tamanho total: 52 bytes

Uso:
  python snap7_variaveis.py                      -> shell interativo
  python snap7_variaveis.py ler                  -> le todas as variaveis
  python snap7_variaveis.py ler Real_Val         -> le uma variavel
  python snap7_variaveis.py escrever Int_Val 123 -> escreve uma variavel
  python snap7_variaveis.py escrever String_Val "Ola mundo"
  python snap7_variaveis.py monitor 0.5          -> monitora todas (Ctrl+C sai)
  python snap7_variaveis.py teste                -> escreve e confere todos os tipos
  Opcoes: --ip 192.168.0.1 --rack 0 --slot 1 --db 1
"""

import argparse
import struct
import sys
import time

from snap7.client import Client

# --------------------------------------------------------------------------
# Configuracao
# --------------------------------------------------------------------------
IP = "192.168.0.1"
RACK = 0
SLOT = 1
DB = 1
DB_SIZE = 52

# nome: (tipo, offset, extra)   extra = bit (Bool) ou tamanho maximo (String)
VARIAVEIS = {
    "Bool_0": ("bool", 0, 0),
    "Bool_1": ("bool", 0, 1),
    "Bool_2": ("bool", 0, 2),
    "Bool_3": ("bool", 0, 3),
    "Bool_4": ("bool", 0, 4),
    "Bool_5": ("bool", 0, 5),
    "Bool_6": ("bool", 0, 6),
    "Bool_7": ("bool", 0, 7),
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

# formatos struct (S7 = big-endian)
FORMATOS = {
    "byte": ">B",
    "int": ">h",
    "uint": ">H",
    "word": ">H",
    "lreal": ">d",
    "dint": ">i",
    "udint": ">I",
    "real": ">f",
    "sint": ">b",
    "usint": ">B",
}


# --------------------------------------------------------------------------
# Codificacao / decodificacao
# --------------------------------------------------------------------------
def _tamanho(tipo, extra):
    if tipo == "bool":
        return 1
    if tipo == "string":
        return 2 + extra
    return struct.calcsize(FORMATOS[tipo])


def _decodificar(tipo, extra, buf, base=0):
    """Converte bytes do PLC em valor Python. 'base' = posicao dentro de buf."""
    if tipo == "bool":
        return bool((buf[base] >> extra) & 1)
    if tipo == "string":
        max_len = buf[base]
        atual = min(buf[base + 1], max_len, extra)
        return bytes(buf[base + 2: base + 2 + atual]).decode("latin-1")
    fmt = FORMATOS[tipo]
    return struct.unpack_from(fmt, buf, base)[0]


def converter_texto(tipo, texto):
    """Converte o texto digitado para o tipo Python adequado."""
    t = texto.strip()
    if tipo == "bool":
        if t.lower() in ("1", "true", "t", "on", "sim", "s", "verdadeiro"):
            return True
        if t.lower() in ("0", "false", "f", "off", "nao", "não", "n", "falso"):
            return False
        raise ValueError("Bool aceita 1/0, true/false, on/off")
    if tipo == "string":
        return texto
    if tipo in ("real", "lreal"):
        return float(t.replace(",", "."))
    return int(t, 0)  # aceita 123, 0xFF, 0b101


def ler(cli, nome):
    tipo, off, extra = VARIAVEIS[nome]
    buf = cli.db_read(DB, off, _tamanho(tipo, extra))
    return _decodificar(tipo, extra, buf)


def escrever(cli, nome, valor):
    tipo, off, extra = VARIAVEIS[nome]
    if tipo == "bool":
        # le o byte, altera so o bit pedido e regrava (nao mexe nos outros bits)
        dado = bytearray(cli.db_read(DB, off, 1))
        if valor:
            dado[0] |= 1 << extra
        else:
            dado[0] &= ~(1 << extra) & 0xFF
        cli.db_write(DB, off, dado)
    elif tipo == "string":
        b = str(valor).encode("latin-1", errors="replace")[:extra]
        dado = bytearray([extra, len(b)]) + bytearray(b.ljust(extra, b"\x00"))
        cli.db_write(DB, off, dado)
    else:
        try:
            dado = bytearray(struct.pack(FORMATOS[tipo], valor))
        except struct.error as e:
            raise ValueError(f"Valor fora da faixa de {tipo.upper()}: {valor}") from e
        cli.db_write(DB, off, dado)


def ler_tudo(cli):
    buf = cli.db_read(DB, 0, DB_SIZE)  # uma unica leitura para o DB inteiro
    return {
        nome: _decodificar(tipo, extra, buf, off)
        for nome, (tipo, off, extra) in VARIAVEIS.items()
    }


# --------------------------------------------------------------------------
# Apresentacao
# --------------------------------------------------------------------------
def _fmt(valor):
    if isinstance(valor, str):
        return repr(valor)
    if isinstance(valor, float):
        return f"{valor:.6g}"
    return str(valor)


def mostrar(valores):
    print(f"{'Variavel':<12} {'Tipo':<7} {'Endereco':<10} Valor")
    print("-" * 52)
    for nome, valor in valores.items():
        tipo, off, extra = VARIAVEIS[nome]
        end = f"DBX{off}.{extra}" if tipo == "bool" else f"DBB{off}"
        print(f"{nome:<12} {tipo.upper():<7} {end:<10} {_fmt(valor)}")


# --------------------------------------------------------------------------
# Comandos
# --------------------------------------------------------------------------
def cmd_ler(cli, nome=None):
    if nome:
        nome = _achar(nome)
        print(f"{nome} = {_fmt(ler(cli, nome))}")
    else:
        mostrar(ler_tudo(cli))


def cmd_escrever(cli, nome, texto):
    nome = _achar(nome)
    tipo = VARIAVEIS[nome][0]
    valor = converter_texto(tipo, texto)
    escrever(cli, nome, valor)
    print(f"{nome} <- {_fmt(valor)}   (lido de volta: {_fmt(ler(cli, nome))})")


def cmd_monitor(cli, intervalo=1.0):
    print("Monitorando... Ctrl+C para parar.\n")
    try:
        while True:
            valores = ler_tudo(cli)
            print("\033[2J\033[H", end="")  # limpa a tela
            mostrar(valores)
            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\nMonitor encerrado.")


def cmd_teste(cli):
    amostras = {
        "Bool_0": True, "Bool_1": False, "Bool_2": True, "Bool_3": False,
        "Bool_4": True, "Bool_5": False, "Bool_6": True, "Bool_7": True,
        "Byte_Val": 0xA5,
        "Int_Val": -1234,
        "UInt_Val": 54321,
        "Word_Val": 0xBEEF,
        "LReal_Val": 3.141592653589793,
        "DInt_Val": -123456789,
        "UDInt_Val": 3000000000,
        "Real_Val": 12.5,
        "String_Val": "Ola PLC",
        "SInt_Val": -100,
        "USInt_Val": 200,
    }
    erros = 0
    for nome, valor in amostras.items():
        escrever(cli, nome, valor)
        lido = ler(cli, nome)
        ok = abs(lido - valor) < 1e-6 if isinstance(valor, float) else lido == valor
        erros += 0 if ok else 1
        print(f"{'OK  ' if ok else 'FALHA'} {nome:<12} escrito={_fmt(valor):<14} lido={_fmt(lido)}")
    print("\nTeste concluido:", "TUDO OK" if erros == 0 else f"{erros} divergencia(s)")


def _achar(nome):
    """Aceita o nome sem diferenciar maiusculas/minusculas."""
    for n in VARIAVEIS:
        if n.lower() == nome.lower():
            return n
    raise KeyError(f"Variavel desconhecida: {nome}. Use 'lista' para ver as opcoes.")


AJUDA = """Comandos:
  lista                      mostra as variaveis disponiveis
  ler [nome]                 le uma variavel (ou todas)
  escrever <nome> <valor>    escreve (ex.: escrever Real_Val 3.14 | escrever String_Val Ola mundo)
  monitor [segundos]         monitora todas (Ctrl+C para parar)
  teste                      escreve e confere todos os tipos
  sair"""


def shell(cli):
    print(AJUDA)
    while True:
        try:
            linha = input("\nsnap7> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not linha:
            continue
        partes = linha.split(maxsplit=2)
        cmd = partes[0].lower()
        try:
            if cmd in ("sair", "exit", "quit"):
                break
            elif cmd in ("ajuda", "help", "?"):
                print(AJUDA)
            elif cmd == "lista":
                for n, (t, o, e) in VARIAVEIS.items():
                    print(f"  {n:<12} {t.upper()}")
            elif cmd == "ler":
                cmd_ler(cli, partes[1] if len(partes) > 1 else None)
            elif cmd == "escrever":
                if len(partes) < 3:
                    print("Uso: escrever <nome> <valor>")
                else:
                    cmd_escrever(cli, partes[1], partes[2])
            elif cmd == "monitor":
                cmd_monitor(cli, float(partes[1]) if len(partes) > 1 else 1.0)
            elif cmd == "teste":
                cmd_teste(cli)
            else:
                print("Comando desconhecido. Digite 'ajuda'.")
        except (KeyError, ValueError) as e:
            print("Erro:", e)
        except Exception as e:  # erros de comunicacao do snap7
            print("Erro de comunicacao:", e)


# --------------------------------------------------------------------------
def main():
    global DB
    p = argparse.ArgumentParser(description="Snap7 <-> TIA Portal V21 (DB_Snap7)")
    p.add_argument("--ip", default=IP)
    p.add_argument("--rack", type=int, default=RACK)
    p.add_argument("--slot", type=int, default=SLOT)
    p.add_argument("--db", type=int, default=DB)
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("ler"); s.add_argument("nome", nargs="?")
    s = sub.add_parser("escrever"); s.add_argument("nome"); s.add_argument("valor", nargs="+")
    s = sub.add_parser("monitor"); s.add_argument("intervalo", nargs="?", type=float, default=1.0)
    sub.add_parser("teste")
    a = p.parse_args()
    DB = a.db

    cli = Client()
    try:
        cli.connect(a.ip, a.rack, a.slot)
    except Exception as e:
        sys.exit(f"Nao foi possivel conectar em {a.ip} (rack {a.rack}, slot {a.slot}): {e}")
    print(f"Conectado em {a.ip} (rack {a.rack}, slot {a.slot}), DB{DB}")

    try:
        if a.cmd == "ler":
            cmd_ler(cli, a.nome)
        elif a.cmd == "escrever":
            cmd_escrever(cli, a.nome, " ".join(a.valor))
        elif a.cmd == "monitor":
            cmd_monitor(cli, a.intervalo)
        elif a.cmd == "teste":
            cmd_teste(cli)
        else:
            shell(cli)
    except (KeyError, ValueError) as e:
        print("Erro:", e)
    finally:
        cli.disconnect()


if __name__ == "__main__":
    main()
