# zensical-carve

Zensical integration for Carve blocks and `.crv` pages, using the Carve 0.2 engine from carve-py `next2` (unreleased). It renders complete pages before the Zensical build. Read the [Carve documentation](https://markup-carve.github.io/carve/) for the language syntax.

## Install

```sh
pip install zensical-carve
```

On this branch the Carve engine is a carve-py `next2` commit that pip builds from source, which needs Rust 1.88 or newer.

## Usage

```sh
zensical-carve prepare
zensical build
```

## Documentation

- [Carve documentation](https://markup-carve.github.io/carve/)
- [Documentation index](docs/README.md)
- [Reference](docs/reference.md)
- [Development](docs/development.md)

## License

[MIT](LICENSE)
