FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /app

# MAVEN_MIRROR 决定容器里的 Maven 走哪个源：
#   aliyun（默认）= 保留下面这份 settings.xml
#   central       = 删掉它，走官方中央仓（境外 runner 上直连更快也更稳）
# ⚠️ ARG 只在声明它的这个 stage 内可见，写到第二个 FROM 之后就取不到值；
#    且删除动作必须排在首次解析依赖之前。
ARG MAVEN_MIRROR=aliyun

COPY docker-maven-settings.xml /root/.m2/settings.xml
RUN if [ "$MAVEN_MIRROR" != "aliyun" ]; then rm -f /root/.m2/settings.xml; fi

COPY pom.xml ./pom.xml
COPY src ./src
RUN mvn -B -ntp -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app

# 版本号在构建期注入（docker build --build-arg，由发布流水线从 git tag 算出）。
# ⚠️ 必须在这个 stage 里**重新声明一次** ARG —— build stage 里那个出了 stage 就不可见。
ARG APP_VERSION=dev
ENV ${APP_ENV_PREFIX}_VERSION=$APP_VERSION

COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
