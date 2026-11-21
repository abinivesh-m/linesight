# -*- coding: utf-8 -*-
"""Visual engine MCP server: generate a self-contained three.js 3D scene (HTML).

Exposes:
  - tool `render_scene` : write an HTML file with a three.js scene from a JSON spec
  - tool `list_scenes`  : list generated scene files

Run:  python -m linesight.mcp_visual --out-dir <dir>
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer


def make_server(out_dir: str) -> MCPServer:
    mcp = MCPServer("linesight-visual")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    @mcp.tool()
    def render_scene(name: str, spec_json: str) -> str:
        """Render a three.js scene to an HTML file.

        spec_json: JSON with optional keys:
          title (str), background (hex), objects (list of {type, position, color, size}),
          camera ( {position, target} ). Supported object types: box, sphere, cylinder, plane.
        """
        try:
            spec = json.loads(spec_json)
        except Exception as e:
            return f"error: bad json: {e}"
        title = spec.get("title", "LineSight 3D scene")
        bg = spec.get("background", "#141414")
        cam = spec.get("camera", {})
        cpos = cam.get("position", [6, 4, 6])
        ctarget = cam.get("target", [0, 0, 0])

        objs = []
        for o in spec.get("objects", []):
            t = o.get("type", "box")
            pos = o.get("position", [0, 0, 0])
            color = o.get("color", "#ff3300")
            size = o.get("size", 1)
            if t == "box":
                objs.append(f"const g=new THREE.BoxGeometry({size},{size},{size});")
            elif t == "sphere":
                objs.append(f"const g=new THREE.SphereGeometry({size/2},32,32);")
            elif t == "cylinder":
                objs.append(f"const g=new THREE.CylinderGeometry({size/2},{size/2},{size*1.5},32);")
            elif t == "plane":
                objs.append(f"const g=new THREE.PlaneGeometry({size*2},{size*2});")
            else:
                objs.append(f"const g=new THREE.BoxGeometry({size},{size},{size});")
            objs.append(f"const m=new THREE.MeshStandardMaterial({{color:'{color}',metalness:0.2,roughness:0.6}});")
            objs.append(f"const mesh=new THREE.Mesh(g,m); mesh.position.set({pos[0]},{pos[1]},{pos[2]}); scene.add(mesh);")

        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>html,body{{margin:0;height:100%;background:{bg};overflow:hidden;font-family:Arial,sans-serif}}
#info{{position:absolute;top:12px;left:12px;color:#fff;font-size:14px;opacity:.85}}</style>
</head><body>
<div id="info">{title}</div>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js"}}}}</script>
<script type="module">
import * as THREE from 'three';
import {{OrbitControls}} from 'https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js';
const scene=new THREE.Scene(); scene.background=new THREE.Color('{bg}');
const camera=new THREE.PerspectiveCamera(60,innerWidth/innerHeight,0.1,1000);
camera.position.set({cpos[0]},{cpos[1]},{cpos[2]});
const renderer=new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(innerWidth,innerHeight); document.body.appendChild(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement); controls.target.set({ctarget[0]},{ctarget[1]},{ctarget[2]});
const amb=new THREE.AmbientLight(0xffffff,0.5); scene.add(amb);
const dir=new THREE.DirectionalLight(0xffffff,1); dir.position.set(5,8,5); scene.add(dir);
const grid=new THREE.GridHelper(20,20,0x444444,0x222222); scene.add(grid);
{chr(10).join(objs)}
function animate(){{requestAnimationFrame(animate); controls.update(); renderer.render(scene,camera);}}
animate();
addEventListener('resize',()=>{{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}});
</script></body></html>"""
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
        path = out / f"{safe}.html"
        path.write_text(html, encoding="utf-8")
        return f"wrote {path} ({len(html)} bytes)"

    @mcp.tool()
    def list_scenes() -> str:
        """List generated scene files."""
        files = sorted(out.glob("*.html"))
        return json.dumps([{"name": f.name, "bytes": f.stat().st_size} for f in files], indent=2)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="docs/scenes")
    args = parser.parse_args()
    mcp = make_server(args.out_dir)
    import asyncio
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()