# OpenBao — High profile (dev mode + UI on localhost)
# Production: replace -dev with a real init/unseal path later.
ui = true

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

storage "inmem" {}
