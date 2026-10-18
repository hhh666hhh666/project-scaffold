package ${PACKAGE}.module.example;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import ${PACKAGE}.security.JwtUtil;
import ${PACKAGE}.support.IntegrationTestBase;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 错误响应的契约样例：**前端的错误处理依赖这里给出的形状**。
 *
 * <p>前端请求层（{@code request.ts}）会按信封的 {@code code} 区分三类错误：
 * 400（调用方传错）、401（未登录）、1000（业务规则不通过）、500（服务器故障）。
 * 这个类只锁前两类里**不需要业务代码**就能触发的部分：
 *
 * <ol>
 *   <li>字段校验失败（{@code @Valid}）→ HTTP 200 + {@code code 400}；</li>
 *   <li>请求体不是合法 JSON → HTTP 200 + {@code code 400}——
 *       若落到兜底分支会返回 500，前端就会把「请求格式错」显示成「系统繁忙」。</li>
 * </ol>
 *
 * <p>业务错误（{@code code 1000}，由 {@code BusinessException} 抛出）不在样例里：
 * 骨架阶段没有真实业务规则可测。第一个业务模块落地时，照这个类的形状补一条。
 *
 * <p>与 {@link ExampleApiIT} 一样继承 {@link IntegrationTestBase}，
 * **不要在子类里再声明容器**。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ExampleErrorContractIT extends IntegrationTestBase {

    @Autowired
    TestRestTemplate restTemplate;

    @Autowired
    JwtUtil jwtUtil;

    @Test
    void blankFieldIsRejectedWithEnvelope400() {
        ResponseEntity<Map<String, Object>> response = post("/api/example/echo", "{\"name\":\"   \"}");

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("code", 400);
        assertThat((String) response.getBody().get("message")).contains("name").contains("不能为空");
    }

    @Test
    void malformedJsonBodyIsRejectedWithEnvelope400() {
        ResponseEntity<Map<String, Object>> response = post("/api/example/echo", "{\"name\":");

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("code", 400);
    }

    /** echo 是受保护接口：这两个用例都必须带合法 token，否则先被鉴权拦成 401。 */
    private ResponseEntity<Map<String, Object>> post(String path, String jsonBody) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(jwtUtil.generateToken(1L));
        return restTemplate.exchange(
                path,
                HttpMethod.POST,
                new HttpEntity<>(jsonBody, headers),
                new ParameterizedTypeReference<>() {
                });
    }
}
