# AI

A collection of independent projects. Each project keeps its source, dependencies, build configuration, documentation and release package in its own directory.

## Projects

### [The Bellworks](bellworks/)

A browser-based 3D Rube Goldberg machine with nine physical stages, built with Three.js and Rapier.

- [Project documentation](bellworks/README.md)
- [Complete offline package](bellworks/Bellworks.zip) — open this file on GitHub and select **Download raw file**.
- [Test results](bellworks/TEST_RESULTS.md)

For development, start in the project directory:

```sh
cd bellworks
npm ci
npm run dev
```

For offline execution, extract `bellworks/Bellworks.zip`, install Node.js 22 in advance, and run `start-offline.bat` in the extracted folder.
