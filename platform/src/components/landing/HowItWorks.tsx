import { Box, Container, Grid, Heading, Stack, Text } from "@chakra-ui/react";

const STEPS = [
  {
    title: "Sube la foto y las medidas",
    body: "Una foto limpia de catálogo, de frente o de tres cuartos, y el ancho, el alto y el fondo en centímetros. Nada más: ningún ajuste técnico.",
  },
  {
    title: "Lo revisamos y lo ves en 3D",
    body: "Ajustamos el modelo a tus medidas (±3 % por eje) y una persona lo revisa antes de enseñártelo. Lo giras, compruebas las medidas y lo colocas en tu casa con el móvil. Gratis.",
  },
  {
    title: "Descárgalo y súbelo a tu tienda",
    body: "GLB para la web y USDZ para iPhone. Shopify muestra el botón «Ver en tu espacio» con el GLB; en WooCommerce o PrestaShop se inserta con un visor estándar.",
  },
] as const;

export function HowItWorks() {
  return (
    <Box as="section" id="como-funciona" py={{ base: 14, md: 24 }} scrollMarginTop="4">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em" mb={{ base: 8, md: 12 }}>
          Cómo funciona
        </Heading>
        <Grid as="ol" listStyleType="none" templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }} gap={{ base: 8, md: 10 }}>
          {STEPS.map((step, index) => (
            <Stack as="li" key={step.title} gap="3">
              <Text fontFamily="heading" fontSize="4xl" lineHeight="1" color="clay.solid" aria-hidden>
                {index + 1}
              </Text>
              <Heading as="h3" fontSize="xl" fontWeight="600" fontFamily="body">
                {step.title}
              </Heading>
              <Text color="fg.muted" textWrap="pretty">
                {step.body}
              </Text>
            </Stack>
          ))}
        </Grid>
      </Container>
    </Box>
  );
}
