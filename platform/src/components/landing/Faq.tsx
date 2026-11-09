import { Box, Container, Heading, Stack, Text } from "@chakra-ui/react";

const QUESTIONS: { q: string; a: string }[] = [
  {
    q: "¿Qué fotos funcionan mejor?",
    a: "Una foto de catálogo de frente o de tres cuartos, con fondo claro y sin otros muebles, con la pieza entera en el encuadre y al menos 1.000 px en el lado mayor. Puedes subir hasta 4 fotos de la misma pieza.",
  },
  {
    q: "¿Qué piezas no hacéis?",
    a: "Por ahora, nada de metal, cromo ni vidrio, ni piezas de patas o tubos finos: el reflejo y las proporciones no salen bien y preferimos no cobrarte por ello. Funcionan la madera y la piedra maciza, la cerámica y el tapizado.",
  },
  {
    q: "¿El modelo mide lo que indico?",
    a: "Sí: lo ajustamos a tus medidas con un margen de ±3\u00a0% por eje y lo comprobamos antes de enseñártelo. En el visor ves las medidas antes de descargar nada.",
  },
  {
    q: "¿Qué archivos recibo?",
    a: "Un GLB con texturas 2K, que sirve para cualquier web, y un USDZ para la realidad aumentada del iPhone. Los dos a escala real.",
  },
  {
    q: "¿Cómo se ve en mi casa?",
    a: "Desde el móvil, el botón de realidad aumentada coloca la pieza en tu salón a tamaño real. Funciona en la mayoría de iPhone y Android, sin instalar nada.",
  },
  {
    q: "¿Y si el resultado no me convence?",
    a: "Pide otra versión (hasta dos por pieza) o descártala. Ni lo uno ni lo otro gasta créditos: solo pagas la pieza que descargas.",
  },
  {
    q: "¿Cuánto tarda?",
    a: "No damos un plazo cerrado: depende de la cola de generación y de la revisión. Te avisamos cuando tu pieza esté lista.",
  },
];

export function Faq() {
  return (
    <Box as="section" id="preguntas" py={{ base: 14, md: 24 }} scrollMarginTop="4">
      <Container maxW="3xl" px={{ base: 4, md: 8 }}>
        <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em" mb="8">
          Preguntas frecuentes
        </Heading>
        <Stack gap="0" borderTopWidth="1px" borderColor="border">
          {QUESTIONS.map(({ q, a }) => (
            // Native <details>: no JavaScript needed for the accordion.
            <Box as="details" key={q} borderBottomWidth="1px" borderColor="border" py="4" css={{ "& > summary::-webkit-details-marker": { display: "none" } }}>
              <Box as="summary" cursor="pointer" fontWeight="600" fontSize="lg" listStyleType="none" display="flex" justifyContent="space-between" gap="4">
                {q}
                <Text as="span" color="fg.subtle" aria-hidden>
                  +
                </Text>
              </Box>
              <Text mt="3" color="fg.muted" textWrap="pretty">
                {a}
              </Text>
            </Box>
          ))}
        </Stack>
      </Container>
    </Box>
  );
}
