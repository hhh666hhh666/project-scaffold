package ${PACKAGE}.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    /**
     * 版本号由构建期注入（镜像的 ENV，源头是 git tag）。默认 dev 只服务本机裸跑。
     * ⚠️ 别把「产品代次」写进 version 字段——那是 API 版本的位置，占着它会误导。
     */
    @Bean
    public OpenAPI openApi(@Value("${CONFIG_VERSION_ANNOTATION}") String version) {
        return new OpenAPI().info(new Info()
                .title("${PROJECT_NAME} API")
                .version(version)
                .description("接口文档"));
    }
}
