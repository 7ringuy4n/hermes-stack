# Minimal YARA-style signatures (YARA-X optional; these always run as layer yara).
rule Suspicious_Eval_Exec {
  meta:
    description = "eval/exec obfuscation"
  strings:
    $a = "eval(" ascii
    $b = "exec(" ascii
    $c = "__import__('os')" ascii
    $d = "subprocess.Popen" ascii
  condition:
    2 of them
}

rule Eicar_Test {
  meta:
    description = "EICAR test string"
  strings:
    $eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*" ascii
  condition:
    $eicar
}

rule Crypto_Miner_Hints {
  strings:
    $a = "stratum+tcp" ascii nocase
    $b = "xmrig" ascii nocase
    $c = "coinhive" ascii nocase
  condition:
    any of them
}
