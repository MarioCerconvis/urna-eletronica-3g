# Ansible — 13 terminais + servidor

1. Na máquina da comissão (controle), tenha `minha-eleicao/eleicao/` (manifesto **assinado** + fotos) e
   `minha-eleicao/chaves/` (todas as chaves). Ajuste `pacote_local` e os IPs em `inventory.ini`.
2. `ansible-playbook -i inventory.ini playbook.yml`
3. O playbook copia para cada host **apenas** as chaves do seu papel e remove chaves privadas indevidas;
   o servidor recebe só chaves públicas.
4. Depois de provisionar, **desconecte da rede** urnas e verificadores antes de abrir a seção.

Observação: `docker-compose.yml` do servidor monta `./dados`; ao usar o playbook, aponte a variável `dados`
para `/srv/urna3g/src/deploy/servidor/dados` ou crie um link simbólico.
