// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title Âncora pública de boletins de urna (urna3g)
/// @notice Não guarda votos, nonces nem horários de cédulas: apenas hashes já públicos
///         (SHA-256 do manifesto = id da eleição, hash do boletim assinado, hash final do
///         ledger da seção e hash da cadeia do mural). Ver docs/04-blockchain.md.
contract RegistroEleitoral {
    struct Boletim {
        bytes32 hashBoletim;
        bytes32 hashLedger;
        uint32 totalCedulas;
        uint64 bloco;
        address registrador;
    }

    struct Eleicao {
        address autoridade;
        bool existe;
        bool encerrada;
        bytes32 hashMural;
        string[] secoes;
    }

    mapping(bytes32 => Eleicao) private _eleicoes;
    mapping(bytes32 => mapping(address => bool)) public apuradores;
    mapping(bytes32 => mapping(string => Boletim)) private _boletins;

    event EleicaoCriada(bytes32 indexed eleicaoId, address autoridade, uint256 numApuradores);
    event BoletimRegistrado(
        bytes32 indexed eleicaoId,
        string secao,
        bytes32 hashBoletim,
        bytes32 hashLedger,
        uint32 totalCedulas,
        address registrador
    );
    event EleicaoEncerrada(bytes32 indexed eleicaoId, bytes32 hashMural);

    /// @param eleicaoId SHA-256 do manifesto canônico (o mesmo id embutido em cada cédula)
    /// @param apuradoresAutorizados endereços (um por máquina de apuração) que podem registrar boletins
    function criarEleicao(bytes32 eleicaoId, address[] calldata apuradoresAutorizados) external {
        require(!_eleicoes[eleicaoId].existe, "eleicao ja existe");
        require(apuradoresAutorizados.length > 0, "informe os apuradores");
        Eleicao storage e = _eleicoes[eleicaoId];
        e.autoridade = msg.sender;
        e.existe = true;
        for (uint256 i = 0; i < apuradoresAutorizados.length; i++) {
            apuradores[eleicaoId][apuradoresAutorizados[i]] = true;
        }
        emit EleicaoCriada(eleicaoId, msg.sender, apuradoresAutorizados.length);
    }

    function registrarBoletim(
        bytes32 eleicaoId,
        string calldata secao,
        bytes32 hashBoletim,
        bytes32 hashLedger,
        uint32 totalCedulas
    ) external {
        Eleicao storage e = _eleicoes[eleicaoId];
        require(e.existe, "eleicao desconhecida");
        require(!e.encerrada, "eleicao encerrada");
        require(apuradores[eleicaoId][msg.sender], "apurador nao autorizado");
        require(bytes(secao).length > 0 && bytes(secao).length <= 16, "secao invalida");
        require(_boletins[eleicaoId][secao].bloco == 0, "secao ja registrada");
        _boletins[eleicaoId][secao] = Boletim(hashBoletim, hashLedger, totalCedulas, uint64(block.number), msg.sender);
        e.secoes.push(secao);
        emit BoletimRegistrado(eleicaoId, secao, hashBoletim, hashLedger, totalCedulas, msg.sender);
    }

    /// @notice Só a autoridade que criou a eleição encerra; depois nenhum boletim entra.
    function encerrar(bytes32 eleicaoId, bytes32 hashMural) external {
        Eleicao storage e = _eleicoes[eleicaoId];
        require(e.existe && msg.sender == e.autoridade, "somente a autoridade");
        require(!e.encerrada, "ja encerrada");
        e.encerrada = true;
        e.hashMural = hashMural;
        emit EleicaoEncerrada(eleicaoId, hashMural);
    }

    function boletim(bytes32 eleicaoId, string calldata secao)
        external
        view
        returns (bytes32 hashBoletim, bytes32 hashLedger, uint32 totalCedulas, uint64 bloco, address registrador)
    {
        Boletim storage b = _boletins[eleicaoId][secao];
        return (b.hashBoletim, b.hashLedger, b.totalCedulas, b.bloco, b.registrador);
    }

    function secoes(bytes32 eleicaoId) external view returns (string[] memory) {
        return _eleicoes[eleicaoId].secoes;
    }

    function eleicao(bytes32 eleicaoId)
        external
        view
        returns (address autoridade, bool existe, bool encerrada, bytes32 hashMural, uint256 numSecoes)
    {
        Eleicao storage e = _eleicoes[eleicaoId];
        return (e.autoridade, e.existe, e.encerrada, e.hashMural, e.secoes.length);
    }
}
