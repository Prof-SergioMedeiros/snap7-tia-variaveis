# Snap7 + TIA Portal V21 - Leitura e escrita de variáveis

Projeto de exemplo que lê e escreve variáveis de um PLC S7-1500 (TIA Portal V21) pelo
protocolo S7 usando a biblioteca [python-snap7](https://github.com/gijzelaerr/python-snap7),
com interface gráfica em Tkinter e uma lógica em SCL que reage às variáveis escritas.
Uma simulação pode ser vista no [site](https://prof-sergiomedeiros.github.io/snap7-tia-variaveis/)

Testado com o **PLCSIM Advanced 8 Upd1**.

## Conteúdo

| Arquivo | Descrição |
|---|---|
| `snap7_gui.py` | Interface gráfica (Tkinter): escreve nas entradas e mostra as saídas calculadas pelo PLC |
| `snap7_variaveis.py` | Versão em linha de comando (shell interativo, `ler`, `escrever`, `monitor`, `teste`) |
| `FC_Logica_Snap7.scl` | Fonte SCL da lógica do PLC |
| `tia_export/` | Blocos do TIA exportados em texto (`.s7dcl`): `Main`, `FC_Logica_Snap7`, `DB_Snap7`, `DB_Snap7_Resp`, `DB_Snap7_Aux` |

O projeto TIA (`Snap7_Variaveis.ap21`) não está versionado por ser binário. Se disponível, ele
fica anexado em **Releases** como `.zip`.

## Requisitos

- TIA Portal V21 e CPU S7-1500 (ou PLCSIM Advanced 8 Upd1)
- Python 3 com Tkinter
- `pip install python-snap7` (testado com a versão 3.3.0)

## Configuração no TIA / CPU / PLCSIM

- **PUT/GET habilitado** na CPU (Propriedades > Proteção e segurança > Mecanismos de conexão).
- **DBs com acesso padrão (não otimizado)**, para o Snap7 endereçar por offset absoluto.
- Baixar hardware e software na CPU / PLCSIM.
- Padrão usado nos exemplos: IP `192.168.0.1`, rack `0`, slot `1`.
- Utilizar no PLCSIM a interface TCP/IP Sigle Adapter.

## Uso

```
python snap7_gui.py                       # interface gráfica

python snap7_variaveis.py                 # shell interativo
python snap7_variaveis.py ler
python snap7_variaveis.py ler Real_Val
python snap7_variaveis.py escrever Int_Val 123
python snap7_variaveis.py escrever String_Val "Ola mundo"
python snap7_variaveis.py monitor 0.5
python snap7_variaveis.py teste           # escreve e confere todos os tipos
# opções: --ip 192.168.0.1 --rack 0 --slot 1 --db 1
```

## Layout dos DBs (valores big-endian, como no S7)

### DB1 `DB_Snap7` - entradas (o Python escreve e lê)

| Offset | Variável | Tipo |
|---|---|---|
| 0.0 a 0.7 | `Bool_0` a `Bool_7` | Bool |
| 1 | `Byte_Val` | Byte |
| 2 | `Int_Val` | Int |
| 4 | `UInt_Val` | UInt |
| 6 | `Word_Val` | Word |
| 8 | `LReal_Val` | LReal |
| 16 | `DInt_Val` | DInt |
| 20 | `UDInt_Val` | UDInt |
| 24 | `Real_Val` | Real |
| 28 | `String_Val` | String[20] (22 bytes) |
| 50 | `SInt_Val` | SInt |
| 51 | `USInt_Val` | USInt |

### DB2 `DB_Snap7_Resp` - saídas calculadas pelo PLC (somente leitura)

| Offset | Variável | O que calcula |
|---|---|---|
| 0.0 | `Heartbeat` | alterna a cada 500 ms |
| 0.1 | `E_Bool01` | `Bool_0` AND `Bool_1` |
| 0.2 | `OU_Bool23` | `Bool_2` OR `Bool_3` |
| 0.3 | `NAO_Bool4` | NOT `Bool_4` |
| 0.4 | `Qualquer_Bool` | algum `Bool_0..7` ligado |
| 1 | `Soma_Bits` | quantos `Bool_0..7` estão ligados |
| 2 | `Int_Mais1` | `Int_Val` + 1 |
| 4 | `DInt_Dobro` | `Int_Val` × 2 |
| 8 | `Contador` | +1 a cada 100 ms (`Bool_6` pausa, `Bool_7` zera) |
| 12 | `Real_Fahrenheit` | `Real_Val` × 1,8 + 32 |
| 16 | `LReal_Raiz` | raiz quadrada de abs(`LReal_Val`) |
| 24 | `String_Eco` | `'Eco: '` + `String_Val` (String[30]) |
| 56 | `Len_String` | tamanho de `String_Val` |
| 58 | `Word_Invertida` | NOT `Word_Val` |

O `DB_Snap7_Resp` ainda contém dois timers IEC (`tmrContador`, `tmrHeartbeat`) que ficaram sem uso.

### DB3 `DB_Snap7_Aux`

Guarda o último instante (ms do relógio da CPU) em que o contador e o heartbeat dispararam.
A lógica usa `TIME_TCK` em vez de timers IEC, porque os timers guardados dentro do DB não
disparavam no PLCSIM.

## Observações

- A lógica roda na `FC_Logica_Snap7`, chamada no `Main` (OB1, LAD).
- Escrever um Bool altera só o bit pedido (lê o byte, muda o bit e regrava).
- Strings: o primeiro byte é o tamanho máximo e o segundo o tamanho atual.
