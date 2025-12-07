// app/policies/terms/page.tsx (ajusta o path)

import Header from "@/components/Header";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pt-6 pb-10">
        <Header subtitle="Termos de Serviço" />

        <div className="mt-8 space-y-4 text-sm text-zinc-300">
          <h1 className="text-2xl font-semibold">Termos de Serviço</h1>

          <p>
            Este website disponibiliza informações e comparação de preços de
            forma gratuita e meramente informativa. Não garantimos exatidão,
            disponibilidade contínua ou ausência de erros.
          </p>

          <p>
            Ao utilizar este website, o utilizador concorda em não tentar
            comprometer a segurança do sistema, sobrecarregar a infraestrutura,
            ou utilizar os dados para fins ilegais.
          </p>

          <p>
            Podemos atualizar estes termos ocasionalmente. O uso continuado
            do website após qualquer alteração constitui aceitação dos novos termos.
          </p>
        </div>
      </section>
    </main>
  );
}
