# generate_sample.py
from core.diagram_ir.schema import DiagramIR, Canvas, Node, Group, Edge, Style
from core.drawio.compiler import generate_xml
from core.drawio.xml_validator import validate_drawio_xml


def main():
    ir = DiagramIR(
        canvas=Canvas(width=1200, height=900),
        groups=[
            Group(
                id="region_1",
                type="azure_region",
                label="East US Region",
                x=50,
                y=50,
                width=1100,
                height=800,
                style=Style(stroke="#0078D4", fill="#f0f8ff"),
            ),
            Group(
                id="vnet_1",
                type="azure_vnet",
                label="Production VNet (10.0.0.0/16)",
                x=80,
                y=100,
                width=1040,
                height=720,
                parent="region_1",
                style=Style(stroke="#0078D4", fill="#e6f2ff", line_style="dashed"),
            ),
            Group(
                id="subnet_frontend",
                type="azure_subnet",
                label="Frontend Subnet (10.0.1.0/24)",
                x=120,
                y=160,
                width=450,
                height=600,
                parent="vnet_1",
                style=Style(stroke="#5c2d91", fill="#f3f0f8"),
            ),
            Group(
                id="subnet_backend",
                type="azure_subnet",
                label="Backend Subnet (10.0.2.0/24)",
                x=620,
                y=160,
                width=450,
                height=600,
                parent="vnet_1",
                style=Style(stroke="#5c2d91", fill="#f3f0f8"),
            ),
        ],
        nodes=[
            Node(
                id="afd_1",
                type="azure_front_door",
                label="Front Door",
                x=160,
                y=240,
                width=80,
                height=80,
                parent="subnet_frontend",
            ),
            Node(
                id="app_1",
                type="azure_app_service",
                label="Web App Service",
                x=350,
                y=240,
                width=80,
                height=80,
                parent="subnet_frontend",
            ),
            Node(
                id="apim_1",
                type="azure_apim",
                label="API Gateway",
                x=660,
                y=240,
                width=80,
                height=80,
                parent="subnet_backend",
            ),
            Node(
                id="pg_1",
                type="azure_postgresql",
                label="PostgreSQL DB",
                x=850,
                y=240,
                width=80,
                height=80,
                parent="subnet_backend",
            ),
            Node(
                id="kv_1",
                type="azure_key_vault",
                label="Key Vault",
                x=850,
                y=440,
                width=80,
                height=80,
                parent="subnet_backend",
            ),
            Node(
                id="custom_box",
                type="generic_worker",
                label="Custom Analytics Job",
                x=160,
                y=440,
                width=120,
                height=60,
                parent="subnet_frontend",
            ),
        ],
        edges=[
            Edge(
                id="e1",
                source="afd_1",
                target="app_1",
                label="HTTPS Ingress",
                direction="forward",
                style="solid",
            ),
            Edge(
                id="e2",
                source="app_1",
                target="apim_1",
                label="REST Calls",
                direction="forward",
                style="solid",
            ),
            Edge(
                id="e3",
                source="apim_1",
                target="pg_1",
                label="Read/Write Query",
                direction="forward",
                style="solid",
            ),
            Edge(
                id="e4",
                source="apim_1",
                target="kv_1",
                label="Get Secrets",
                direction="forward",
                style="dashed",
                waypoints=[[700.0, 480.0]],
            ),
        ],
    )

    xml_content = generate_xml(ir)
    validate_drawio_xml(xml_content)

    output_path = "sample_architecture.drawio"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"Successfully generated {output_path}")


if __name__ == "__main__":
    main()
