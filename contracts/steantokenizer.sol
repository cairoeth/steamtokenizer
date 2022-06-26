// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Burnable.sol";

/**
 * @title Steam Tokenizer contract
 * @author Cairo (@ethcairo)
 * @dev ERC721 contract from which users can mint an NFT that is backed by a Steam digital tradeable asset.
 * @dev Not endorsed in any way by Valve Corporation.
 **/
contract SteamTokenizer is ERC721URIStorage, ERC721Burnable {
    string constant baseContractURI = "https://gateway.pinata.cloud/ipfs/QmSY1sSbsSZbWVmDWV8xpC1XHT1ccmu53HhR8Jqk76ZN5Z";
    uint256 private tokenIdCounter;
    address public botAddress = 0x741cB6A6a8dC16363666462769D8dEc996311466;
    string public url = "https://ipfs.io/ipfs/";

    mapping(uint => uint) public escrows;
    mapping(string => bool) private minted;

    constructor() ERC721("Steam Asset", "STEAM") {
        tokenIdCounter = 0;
    }

    /**
    * @dev Burns token to return to specific Steam user
    * @param escrow is the Unix timestamp when the Steam asset is no longer locked by the platform
    * @param uri is the hash of the metadata stored in IPFS
    * @param sig is the signature by the Steam bot to ensure parameters are valid and not modified
    **/
    function mint(uint256 escrow, string memory uri, bytes memory sig) external {
        bytes32 message = keccak256(abi.encodePacked(escrow, uri));
        require(recoverSigner(message, sig) == botAddress, "Invalid signature or parameters");
        require(!minted[uri], "Steam asset already claimed");

        ++tokenIdCounter;
        escrows[tokenIdCounter] = escrow;
        minted[uri] = true;
        _safeMint(msg.sender, tokenIdCounter);
        _setTokenURI(tokenIdCounter, string.concat(url, uri));
    }

    /**
    * @dev Burns token to return to specific Steam user
    * @param tokenId is the ID of the token to burn
    **/
    function _burn(uint256 tokenId) internal override(ERC721, ERC721URIStorage) {
        require(block.timestamp > escrows[tokenId], "Cooldown period not finished");
        super._burn(tokenId);
    }

    /**
    * @dev Returns token metadata
    * @param tokenId is the ID of the token with the associated metadata
    **/
    function tokenURI(uint256 tokenId) public view override(ERC721, ERC721URIStorage) returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    /**
    * @dev Returns contract metadata
    **/
    function contractURI() public pure returns (string memory) {
        return baseContractURI;
    }

    /**
    * @dev Implementation of ecrecover to verify signature
    **/
    function recoverSigner(bytes32 message, bytes memory sig)
        public
        pure
        returns (address)
    {
        uint8 v;
        bytes32 r;
        bytes32 s;
        (v, r, s) = splitSignature(sig);
        return ecrecover(message, v, r, s);
    }

    /**
    * @dev Separates a tx signature into v, r, and s values
    **/
    function splitSignature(bytes memory sig)
        public
        pure
        returns (uint8, bytes32, bytes32)
    {
        require(sig.length == 65);
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            // First 32 bytes, after the length prefix
            r := mload(add(sig, 32))
            // Second 32 bytes
            s := mload(add(sig, 64))
            // Final byte (first byte of the next 32 bytes)
            v := byte(0, mload(add(sig, 96)))
        }

        return (v, r, s);
    }

}
