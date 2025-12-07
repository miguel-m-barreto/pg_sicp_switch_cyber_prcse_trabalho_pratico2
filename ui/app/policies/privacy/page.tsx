// app/policies/privacy/page.tsx (ajusta o path conforme a tua estrutura)

import Header from "@/components/Header";

export default function PrivacyPolicy() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pt-6 pb-10">
        <Header subtitle="Política de Privacidade" />

        <div className="mt-8 space-y-4 text-sm text-zinc-300">
          <h1 className="text-2xl font-semibold">Política de Privacidade</h1>

          <p>
            Este website utiliza o Google AdSense para apresentar anúncios.
            O Google pode utilizar cookies, incluindo cookies de publicidade,
            para personalizar anúncios com base nas suas visitas anteriores
            a este e a outros websites.
          </p>

          <h2 className="text-lg font-medium mt-4">Cookies e Dados de Utilização</h2>
          <p>
            O Google utiliza cookies para exibir anúncios e medir o desempenho
            dos mesmos. Pode consultar como o Google utiliza dados em{" "}
            <a
              href="https://policies.google.com/technologies/partner-sites"
              className="underline"
              target="_blank"
            >
              https://policies.google.com/technologies/partner-sites
            </a>.
          </p>

          <h2 className="text-lg font-medium mt-4">Consentimento</h2>
          <p>
            Utilizadores do Espaço Económico Europeu (EEE), Reino Unido e Suíça
            verão um aviso de consentimento conforme os requisitos da legislação
            de privacidade. A gestão do consentimento é assegurada pelo Google CMP.
          </p>

          <h2 className="text-lg font-medium mt-4">Contacto</h2>
          <p>
            Para qualquer questão relacionada com privacidade, pode contactar:
            <br />
            <span className="font-mono">postgrad.grupo@gmail.com</span>
          </p>
        </div>
      </section>
    </main>
  );
}
