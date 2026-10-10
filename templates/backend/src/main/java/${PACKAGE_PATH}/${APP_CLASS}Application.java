package ${PACKAGE};

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("${PACKAGE}.**.mapper")
public class ${APP_CLASS}Application {

    public static void main(String[] args) {
        SpringApplication.run(${APP_CLASS}Application.class, args);
    }
}
