import { Box, Container, Heading, Link, List, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ResetConsentButton } from "@/components/CookieConsent";
import { SiteFooter, SiteHeader } from "@/components/landing/SiteHeader";
import { PRODUCT_NAME } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacidad y cookies",
  description: `Qué datos trata ${PRODUCT_NAME}, para qué, con quién y qué cookies usa.`,
  alternates: { canonical: "/privacidad" },
};

// TODO(Jorge): legal name and tax id of the owner once the company is set.
const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || null;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack as="section" gap="3">
      <Heading as="h2" fontSize={{ base: "xl", md: "2xl" }} fontWeight="500">
        {title}
      </Heading>
      {children}
    </Stack>
  );
}

function Contact() {
  return CONTACT_EMAIL ? (
    <Link href={`mailto:${CONTACT_EMAIL}`} color="clay.fg" fontWeight="600">
      {CONTACT_EMAIL}
    </Link>
  ) : (
    <>el correo de contacto de la web</>
  );
}

export default function PrivacyPage() {
  return (
    <>
      <SiteHeader />
      <Container as="main" maxW="3xl" px={{ base: 4, md: 8 }} py={{ base: 10, md: 16 }}>
        <Stack gap="10" lineHeight="1.7">
          <Stack gap="3">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              Privacidad y cookies
            </Heading>
            <Text color="fg.muted">
              Lo esencial, sin letra pequeña. Si tienes cualquier duda, escríbenos a <Contact />.
            </Text>
          </Stack>

          <Section title="Qué datos tratamos y para qué">
            <List.Root gap="2" ps="5">
              <List.Item>
                <strong>Tu correo electrónico</strong>, para crear tu cuenta y enviarte el enlace de acceso y los avisos
                de tus piezas (por ejemplo, cuando una pieza está lista).
              </List.Item>
              <List.Item>
                <strong>Las fotos, medidas y notas de tus muebles</strong>, para generar el modelo 3D, revisarlo antes
                de enseñártelo y entregártelo.
              </List.Item>
              <List.Item>
                <strong>Tus compras y créditos</strong>: paquete, importe y movimientos de saldo. No vemos ni guardamos
                los datos de tu tarjeta; el pago lo gestiona Stripe.
              </List.Item>
              <List.Item>
                <strong>Cómo llegaste</strong> (parámetros de la campaña o el enlace, como <code>utm_source</code>), para
                saber qué anuncios funcionan. Se guarda con tu cuenta al registrarte.
              </List.Item>
            </List.Root>
            <Text>
              La base legal es el contrato (darte el servicio que pides), nuestro interés legítimo en saber de dónde
              vienen nuestros clientes y, para las cookies de medición, tu consentimiento. No vendemos tus datos.
            </Text>
          </Section>

          <Section title="Con quién los compartimos">
            <Text>Solo con los proveedores que necesitamos para dar el servicio, que tratan los datos por encargo nuestro:</Text>
            <List.Root gap="2" ps="5">
              <List.Item>
                <strong>Supabase</strong>: cuentas, base de datos y archivos, en servidores de la Unión Europea
                (Irlanda).
              </List.Item>
              <List.Item>
                <strong>Stripe</strong>: cobro de los paquetes de créditos.
              </List.Item>
              <List.Item>
                <strong>Resend</strong>: envío de los correos de aviso.
              </List.Item>
              <List.Item>
                <strong>Vercel</strong>: alojamiento de la web.
              </List.Item>
              <List.Item>
                <strong>Meta y Google</strong>, solo si aceptas las cookies de medición (ver abajo).
              </List.Item>
            </List.Root>
            <Text>
              Algunos de estos proveedores pueden tratar datos fuera de la Unión Europea con las garantías que exige el
              RGPD (cláusulas contractuales tipo o marcos de adecuación).
            </Text>
          </Section>

          <Section title="Cuánto tiempo los guardamos">
            <Text>
              Mientras tengas cuenta. Si nos pides borrarla, eliminamos tu cuenta, tus fotos y tus modelos; los datos de
              las compras se conservan el tiempo que exige la ley fiscal.
            </Text>
          </Section>

          <Section title="Cookies">
            <List.Root gap="2" ps="5">
              <List.Item>
                <strong>Necesarias</strong> (siempre activas): la sesión para que sigas dentro de tu cuenta y
                <code> sh_attr</code>, que recuerda durante 90 días de qué campaña o enlace llegaste. Son nuestras y no
                se comparten.
              </List.Item>
              <List.Item>
                <strong>De medición</strong> (solo si las aceptas): Meta Pixel y Google Analytics, para saber si los
                anuncios atraen a gente que crea y compra piezas. Si las rechazas, no se carga ninguno de los dos.
              </List.Item>
            </List.Root>
            <Text>
              Tu elección se guarda en este navegador durante 180 días. Puedes cambiarla cuando quieras.
            </Text>
            <Box>
              <ResetConsentButton />
            </Box>
          </Section>

          <Section title="Tus derechos">
            <Text>
              Puedes pedir acceso, corrección, borrado, limitación, portabilidad u oponerte al tratamiento escribiendo a{" "}
              <Contact />. Si crees que no hemos atendido bien tu petición, puedes reclamar ante la Agencia Española de
              Protección de Datos (aepd.es).
            </Text>
          </Section>
        </Stack>
      </Container>
      <SiteFooter />
    </>
  );
}
